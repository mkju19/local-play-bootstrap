from typing import Union, Callable, List, Optional

from sharpy.plans import BuildOrder
from sharpy.plans.acts import ActBase
from sharpy.plans.tactics import WarnBuildMacro


class WithOpener(BuildOrder):
    def __init__(
        self,
        warning: Optional[WarnBuildMacro],
        orders: Union[
            Union[ActBase, Callable[["Knowledge"], bool]], List[Union[ActBase, Callable[["Knowledge"], bool]]]
        ],
        *argv
    ):
        super().__init__(orders, *argv)
        self.warning = warning
        self.opener = self.orders[0]
        if warning:
            self.orders.insert(0, warning)
        self.opener_completed = False

    async def execute(self) -> bool:
        if self.opener_completed:
            return await super().execute()
        else:
            if self.warning:
                await self.warning.execute()

            if await self.opener.execute():
                self.opener_completed = True
            return False
