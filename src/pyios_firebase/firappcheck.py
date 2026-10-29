from rubicon.objc import ObjCClass

FIRAppCheck = ObjCClass("FIRAppCheck")
FIRAppCheckDebugProviderFactory = ObjCClass("FIRAppCheckDebugProviderFactory")


def initialize_debug_appcheck():
    # 1. App Check first
    provider_factory = FIRAppCheckDebugProviderFactory.alloc().init()
    FIRAppCheck.setAppCheckProviderFactory_(provider_factory)
    # 2. Then configure Firebase
