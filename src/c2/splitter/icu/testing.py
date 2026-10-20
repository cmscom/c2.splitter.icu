from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer

from typing import Any

import c2.splitter.icu


class Layer(PloneSandboxLayer):
    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app: Any, configurationContext: Any) -> None:
        # z3c.autoinclude is disabled in the Plone fixture base layer.
        self.loadZCML(package=c2.splitter.icu)

    def setUpPloneSite(self, portal: Any) -> None:
        applyProfile(portal, "c2.splitter.icu:default")


FIXTURE = Layer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name="C2.Splitter.IcuLayer:IntegrationTesting",
)

FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE,),
    name="C2.Splitter.IcuLayer:FunctionalTesting",
)
