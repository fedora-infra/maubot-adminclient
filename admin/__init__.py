from maubot import Plugin
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from .commands import Commands

NL = "      \n"


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("command")
        helper.copy("controlroom")


class Admin(Plugin):
    async def start(self) -> None:
        self.config.load_and_update()
        self.register_handler_class(Commands(self))

    async def stop(self) -> None:
        pass

    @classmethod
    def get_config_class(cls) -> type[BaseProxyConfig]:
        return Config
