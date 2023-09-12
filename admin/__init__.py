from typing import Type
from functools import wraps

from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper


from maubot import Plugin, MessageEvent
from maubot.handlers import command, event
from mautrix.types import EventType, StateEvent, Membership
from mautrix.errors import MNotFound
from mautrix.errors.request import MForbidden, MUnknown


NL = "      \n"

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("command")
        helper.copy("controlroom")


class Admin(Plugin):
    async def start(self) -> None:
        self.config.load_and_update()

    async def stop(self) -> None:
        pass

    def get_command_name(self) -> str:
        return self.config.get("command", "admin")

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def _is_direct_chat(self, room_id):
        members = await self.client.get_joined_members(room_id)
        # i can't find a better way to check if a room is a DM or not, so this is it.
        # we check if the room as only 2 users, and if one of those members is the bot.
        if len(members) == 2 and self.client.mxid in members:
            return [i for i in list(members.keys()) if i != self.client.mxid][0]
        return False

    def _is_controlroom(self, evt):
        return self.config.get("controlroom", None) == evt.room_id
    
    async def _get_canonical_alias(self, room_id: str) -> str:
        try:
            existing_event = await self.client.get_state_event(room_id, EventType.ROOM_CANONICAL_ALIAS)
            canonical_alias = existing_event.canonical_alias
        except MNotFound:
            canonical_alias = None
        return canonical_alias

    @command.new(name=get_command_name, help="Admin Commands", require_subcommand=False)
    async def admin(self, evt: MessageEvent) -> None:
        is_controlroom = self._is_controlroom(evt)
        if is_controlroom:
            await evt.respond(self.admin.__mb_full_help__)
    
    @admin.subcommand(help="List Rooms this bot is in")
    async def list(self, evt:MessageEvent) -> None:
        is_controlroom = self._is_controlroom(evt)
        if is_controlroom:
            joined_rooms = await self.client.get_joined_rooms()
            response = ""
            for room_id in joined_rooms:
                canonical_alias = await self._get_canonical_alias(room_id)
                if canonical_alias:
                    response = f"{response}* {canonical_alias} - {room_id}{NL}"
                else:
                    dm_user = await self._is_direct_chat(room_id)
                    if dm_user:                        
                        response = f"{response}* {dm_user} - {room_id}{NL}"
                    else:
                        members = await self.client.get_joined_members(room_id)
                        if len(members) == 1 and self.client.mxid in members:
                            # this is a room that the bot is in by itself. so lonely :(
                            # so just leave the room.
                            await self.client.leave_room(room_id)
                        else:
                            if room_id == self.config["controlroom"]:
                                response = f"{response}* {room_id} (__the control room__){NL}"
                            else:
                                response = f"{response}* unknown room with {list(members.keys())} - {room_id}{NL}"
            await evt.respond(response)

    @admin.subcommand(help="Leave a Room")
    @command.argument("room_id", required=True)
    async def leave(self, evt:MessageEvent, room_id:str) -> None:
        is_controlroom = self._is_controlroom(evt)
        if is_controlroom:
            if room_id[0] != "!":
                await evt.reply("please enter a valid room ID (e.g. !umlOfwGjmBRiSzUyaa:fedora.im )")
            else:
                joined_rooms = await self.client.get_joined_rooms()
                if room_id in joined_rooms:
                    await self.client.leave_room(room_id)
                    await evt.respond(f"left room {room_id}")
                else:
                    await evt.respond("i dont appear to be in that room, so i cannot leave it")

    @admin.subcommand(help="Join a Room")
    @command.argument("room_id_or_alias", required=True)
    async def join(self, evt:MessageEvent, room_id_or_alias:str) -> None:
        is_controlroom = self._is_controlroom(evt)
        if is_controlroom:
            await self.client.join_room(room_id_or_alias)
    
    @admin.subcommand(help="Send a message to a room")
    @command.argument("room_id", required=True)
    @command.argument("text", pass_raw=True, required=True)
    async def send_message(self, evt:MessageEvent, room_id:str, text: str) -> None:
        is_controlroom = _self.is_controlroom(evt)
        if is_controlroom:
            if not room_id or not text:
                pass
                await evt.reply("need a room Id and a message")
            else:
                await self.client.send_text(room_id, text)
