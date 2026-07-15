import os
from openai import OpenAI
from dotenv import load_dotenv

from config import get_settings

# -----------------------------------------
# 1. SETUP
# -----------------------------------------

load_dotenv()
_settings = get_settings()

# Gemini via its OpenAI-compatible endpoint — the chat.completions calls below
# stay unchanged; only the client's base_url/key/model point at Google now.
client = OpenAI(
    api_key=_settings.google_api_key,
    base_url=_settings.gemini_base_url,
)


# -----------------------------------------
# 2. FORMAT DISEASE NAME
# -----------------------------------------

def format_disease_name(raw_name: str) -> str:
    """
    "Potato___Fungi"       -> "Potato Fungi"
    "Tomato___Late_blight" -> "Tomato Late Blight"
    """
    name = raw_name.replace("___", " ").replace("_", " ")
    return name.title()


# -----------------------------------------
# 3. SYSTEM PROMPT
# -----------------------------------------


# from rag.prompts import (
#     DISEASE_DETECTION_SYSTEM_PROMPT_TEMPLATE,
#     DISEASE_LANGUAGE_INSTRUCTION_ENGLISH,
#     DISEASE_LANGUAGE_INSTRUCTION_NEPALI,
#     DISEASE_FIRST_MESSAGE_ENGLISH_TEMPLATE,
#     DISEASE_FIRST_MESSAGE_NEPALI_TEMPLATE,
# )

# def build_system_prompt(language: str, weather_text: str = "", rag_context: str = "") -> str:
#     """
#     Builds system prompt for disease detection.
    
#     Args:
#         language: "english" or "nepali"
#         weather_text: weather context (e.g., "High humidity, recent rain expected")
    
#     Returns:
#         Complete system prompt ready for LLM
#     """
    
#     # Select language instruction
#     if language == "nepali":
#         language_instruction = DISEASE_LANGUAGE_INSTRUCTION_NEPALI
#     else:
#         language_instruction = DISEASE_LANGUAGE_INSTRUCTION_ENGLISH
    
#     # Format weather context
#     if weather_text:
#         weather_context = f"Current Weather Conditions:\n{weather_text}\n\nUse the farmer location and weather data above to give specific, location-aware and weather-aware advice. Adjust treatment timing, disease risk, and planting advice based on current conditions."
#     else:
#         weather_context = "Note: Weather data not available. Provide general advice."
    
#     # Build final prompt
#     rag_section = f"\n\nRelevant knowledge from agricultural references:\n{rag_context}" if rag_context else ""

#     system_prompt = DISEASE_DETECTION_SYSTEM_PROMPT_TEMPLATE.format(
#         weather_context=weather_context,
#         language_instruction=language_instruction
#     ) + rag_section
    
#     return system_prompt


from rag.prompts import (
    PROMPT_BASE, PROMPT_LANGUAGE_NEPALI, PROMPT_LANGUAGE_ENGLISH,
    PROMPT_FIRST_MESSAGE, PROMPT_TREATMENT, PROMPT_FOLLOWUP,
    PROMPT_EXPERT, PROMPT_SUGGESTIONS,
    DISEASE_FIRST_MESSAGE_ENGLISH_TEMPLATE,
    DISEASE_FIRST_MESSAGE_NEPALI_TEMPLATE,
)

TREATMENT_WORDS = [
    "upchar", "treatment", "उपचार", "chemical", "rasaynik",
    "organic", "jaivik", "dawa", "medicine", "औषधि", "gharelu", "homemade", "ilaj"
]

def detect_intent(message: str) -> str:
    if any(w in message.lower() for w in TREATMENT_WORDS):
        return "treatment"
    return "general"

def build_system_prompt(
    language: str,
    weather_text: str = "",
    rag_context: str = "",
    is_first_message: bool = False,
    user_message: str = ""
) -> str:

    prompt = PROMPT_BASE
    prompt += PROMPT_LANGUAGE_NEPALI if language == "nepali" else PROMPT_LANGUAGE_ENGLISH

    if is_first_message:
        prompt += PROMPT_FIRST_MESSAGE
    elif detect_intent(user_message) == "treatment":
        prompt += PROMPT_TREATMENT
    else:
        prompt += PROMPT_FOLLOWUP

    prompt += PROMPT_EXPERT

    if weather_text:
        prompt += f"\nCurrent Weather: {weather_text}"

    if rag_context:
        prompt += f"\nAgricultural reference:\n{rag_context}"

    prompt += PROMPT_SUGGESTIONS

    return prompt



# -----------------------------------------
# 4. FIRST MESSAGE PROMPT
# -----------------------------------------

def build_first_message(disease_raw: str, crop_type: str, language: str) -> str:
    """
    Builds the first user message when disease is detected.
    
    Args:
        disease_raw: raw class name e.g. "Potato___Fungi"
        crop_type: "Potato" or "Tomato"
        language: "english" or "nepali"
    
    Returns:
        Formatted first message
    """
    
    disease_readable = format_disease_name(disease_raw)
    
    if language == "nepali":
        return DISEASE_FIRST_MESSAGE_NEPALI_TEMPLATE.format(
            crop_type=crop_type,
            disease_readable=disease_readable
        )
    else:
        return DISEASE_FIRST_MESSAGE_ENGLISH_TEMPLATE.format(
            crop_type=crop_type,
            disease_readable=disease_readable
        )

# -----------------------------------------
# 5. GET FIRST RECOMMENDATION
# -----------------------------------------

def get_first_recommendation(
    disease_raw: str,
    crop_type: str,
    language: str = "english",
    weather_text: str = "",
    rag_context: str = ""
) -> dict:
    """
    Called when disease is first detected.
    Starts the conversation and returns initial response + conversation history.

    Args:
        disease_raw  : raw class name e.g. "Potato___Fungi"
        crop_type    : "Potato" or "Tomato"
        language     : "english" or "nepali"
        weather_text : description of current weather conditions

    Returns:
        {
            "disease_name"        : "Potato Fungi",
            "crop_type"           : "Potato",
            "response"            : "Grok's first response...",
            "conversation_history": [...],   <- save this for follow ups
            "error"               : None
        }
    """
    disease_readable = format_disease_name(disease_raw)
    # Handle healthy plant — no LLM needed
    if "healthy" in disease_raw.lower():
        return {
            "disease_name": disease_readable,
            "crop_type": crop_type,
            "response": "तपाईंको बाली स्वस्थ देखिन्छ! राम्रो हेरचाह गर्नुभएको छ। नियमित सिँचाइ र मलखाद दिँदै राख्नुहोस्।\n\nSUGGESTIONS: मल कहिले दिने? | सिँचाइ कति गर्ने? | रोकथाम कसरी गर्ने?",
            "conversation_history": [],
            "error": None,
        }


    system_prompt   = build_system_prompt(language, weather_text, rag_context, is_first_message=True)
    first_message   = build_first_message(disease_raw, crop_type, language)

    # Start conversation history with first user message
    conversation_history = [
        {"role": "user", "content": first_message}
    ]

    try:
        print(f"System prompt: {len(system_prompt)//4} tokens (est)")
        print(f"RAG context: {len(rag_context)//4} tokens (est)")
        print(f"First message: {len(first_message)//4} tokens (est)")
        print(f"TOTAL INPUT EST: {(len(system_prompt)+len(rag_context)+len(first_message))//4} tokens")
        response = client.chat.completions.create(
            model=_settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                *conversation_history,
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        grok_response = response.choices[0].message.content.strip()

        # Append Grok's response to history so next message has full context
        conversation_history.append({
            "role": "assistant",
            "content": grok_response
        })

        return {
            "disease_name"        : disease_readable,
            "crop_type"           : crop_type,
            "response"            : grok_response,
            "conversation_history": conversation_history,
            "error"               : None,
        }

    except Exception as e:
        return {
            "disease_name"        : disease_readable,
            "crop_type"           : crop_type,
            "response"            : None,
            "conversation_history": [],
            "error"               : f"Could not fetch recommendation: {str(e)}",
        }


# -----------------------------------------
# 6. FOLLOW UP QUESTION
# -----------------------------------------

def get_followup_response(
    user_message: str,
    conversation_history: list,
    language: str = "english",
    weather_text: str = "",
    rag_context: str = "" 
) -> dict:
    """
    Called when farmer asks a follow up question.
    Uses full conversation history so Grok remembers context.

    Args:
        user_message         : farmer's follow up question
        conversation_history : full history from previous responses
        language             : "english" or "nepali"


    Returns:
        {
            "response"            : "Grok's follow up response...",
            "conversation_history": [...],   <- updated history
            "error"               : None
        }
    """

    system_prompt = build_system_prompt(language, weather_text, rag_context, user_message=user_message)

    # Append new user message to existing history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    try:
        response = client.chat.completions.create(
            model=_settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                *conversation_history,   # full history = Grok remembers everything
            ],
            max_tokens=500,
            temperature=0.3,
        )

        grok_response = response.choices[0].message.content.strip()

        # Append Grok's response to history for next turn
        conversation_history.append({
            "role": "assistant",
            "content": grok_response
        })

        return {
            "response"            : grok_response,
            "conversation_history": conversation_history,
            "error"               : None,
        }

    except Exception as e:
        return {
            "response"            : None,
            "conversation_history": conversation_history,
            "error"               : f"Could not get response: {str(e)}",
        }


# -----------------------------------------
# 7. LOCAL TEST
# -----------------------------------------

if __name__ == "__main__":

    print("=" * 50)
    print("Testing recommender with conversation memory")
    print("=" * 50)

    # Simulate first detection
    print("\nStep 1 — First disease detection (English)...")
    result = get_first_recommendation(
        disease_raw="Potato___Fungi",
        crop_type="Potato",
        language="english"
    )

    if result["error"]:
        print(f"Error: {result['error']}")
    else:
        print(f"Disease  : {result['disease_name']}")
        print(f"Response :\n{result['response']}")

        # Save history for follow up
        history = result["conversation_history"]

        # Simulate follow up question
        print("\nStep 2 — Follow up: asking for treatment...")
        followup = get_followup_response(
            user_message="Yes, please tell me the treatment",
            conversation_history=history,
            language="english"
        )

        if followup["error"]:
            print(f"Error: {followup['error']}")
        else:
            print(f"Response:\n{followup['response']}")

            # Simulate second follow up
            print("\nStep 3 — Follow up: asking for prevention...")
            followup2 = get_followup_response(
                user_message="What about prevention for next season?",
                conversation_history=followup["conversation_history"],
                language="english"
            )
            print(f"Response:\n{followup2['response']}")

    # Test Nepali
    print("\n" + "=" * 50)
    print("Testing Nepali language...")
    print("=" * 50)

    nepali_result = get_first_recommendation(
        disease_raw="Tomato___Late_blight",
        crop_type="Tomato",
        language="nepali"
    )

    if nepali_result["error"]:
        print(f"Error: {nepali_result['error']}")
    else:
        print(f"Response:\n{nepali_result['response']}")