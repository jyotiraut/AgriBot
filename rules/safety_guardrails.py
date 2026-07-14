class SafetyFlag:
    def __init__(self, severity, message):
        self.severity = severity
        self.message = message

def run_safety_checks(crop, das, fertilizer_name, fertilizer_kg_per_ha, pesticide_name=None, pesticide_ml_per_ha=None):
    flags = []
    # Basic logic
    if fertilizer_kg_per_ha is not None and fertilizer_kg_per_ha > 100:
        flags.append(SafetyFlag("CRITICAL", f"Excessive {fertilizer_name} applied! Maximum allowed is 100 kg/ha."))
    
    if pesticide_ml_per_ha is not None and pesticide_ml_per_ha > 1000:
        flags.append(SafetyFlag("CRITICAL", f"Excessive {pesticide_name} applied! Maximum allowed is 1000 ml/ha."))
        
    return flags
