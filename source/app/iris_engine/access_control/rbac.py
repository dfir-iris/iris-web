from typing import Literal


# ---- entitlements (where & what?) -------------------------------------------

ENTITLEMENT_GRANTS = Literal["read", "create", "update", "delete"]
"""grant types allowed on an entitlement"""


class Entitlement:
    """An Entitlement represents access to a group of resources/specific resource"""

    grants: list[ENTITLEMENT_GRANTS] = []
    """the grant(s) (what kind of activity is this?)"""

    resources: list[str] = []
    """the applicable resource by name
    
    Values:
        - "Case", allows 'grants' on 'Case' resources
        - "Case:42", allows 'grants' on 'Case' #42 only
    """


# ---- roles (who & where?) ---------------------------------------------------

class Role:
    """A Role represents a group of entitlements"""

    entitlements: list[Entitlement] = []
    """list of Entitlements granted to this role"""

    # ---- logic ----

    def __init__(self, entitlements: list[Entitlement]) -> None:
        self.entitlements = entitlements

    # ---- utils ----

    @classmethod
    def entitlement_check(self, *entitlement: list[Entitlement]) -> bool:
        """Check if the entitlement passed is granted by this role

        Args:
            entitlement (list[Entitlement]): The Entitlement to check

        Returns:
            bool: _description_
        """

        # todo: implement this check logic

        return False
