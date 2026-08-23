class HydrationKineticsError(Exception):
    pass

class DataParserError(HydrationKineticsError):
    pass

class KineticsCalculationError(HydrationKineticsError):
    pass