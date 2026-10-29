from rubicon.objc import ObjCClass

FIRAuth = ObjCClass("FIRAuth")


class User:
    def __init__(self):
        self.auth = FIRAuth.auth()
        self.user = self.auth.currentUser

    @property
    def email(self):
        return self.user.email

    @property
    def uid(self):
        return self.user.uid

    @property
    def display_name(self):
        return self.user.displayName
