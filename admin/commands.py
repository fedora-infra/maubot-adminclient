import re

from maubot import MessageEvent
from maubot.handlers import command
from mautrix.errors import MNotFound
from mautrix.errors.request import MForbidden, MUnknown
from mautrix.types import EventType

from .constants import NL
from .handler import Handler


class Commands(Handler):
    def get_command_name(self) -> str:
        return self.plugin.config.get("command", "admin")

    async def _is_direct_chat(self, room_id):
        members = await self.plugin.client.get_joined_members(room_id)
        # i can't find a better way to check if a room is a DM or not, so this is it.
        # we check if the room as only 2 users, and if one of those members is the bot.
        if len(members) == 2 and self.plugin.client.mxid in members:
            return next(i for i in list(members.keys()) if i != self.plugin.client.mxid)
        return False

    def _is_controlroom(self, evt):
        return self.plugin.config.get("controlroom", None) == evt.room_id

    async def _get_canonical_alias(self, room_id: str) -> str:
        try:
            existing_event = await self.plugin.client.get_state_event(
                room_id, EventType.ROOM_CANONICAL_ALIAS
            )
            canonical_alias = existing_event.canonical_alias
        except MNotFound:
            canonical_alias = None
        return canonical_alias

    def _get_first_mxid_link(self, evt):
        if evt.content.formatted_body:
            matrixlinks = re.findall(
                r'href=[\'"]?http[s]?://matrix.to/#/([^\'" >]+)',
                evt.content.formatted_body,
            )
            if len(matrixlinks) >= 1:
                return matrixlinks[0]

    @command.new(name=get_command_name, help="Admin Commands", require_subcommand=False)
    async def admin(self, evt: MessageEvent) -> None:
        is_controlroom = self._is_controlroom(evt)
        if is_controlroom:
            await evt.respond(self.admin.__mb_full_help__)

    @admin.subcommand(help="List Rooms this bot is in")
    async def list(self, evt: MessageEvent) -> None:
        is_controlroom = self._is_controlroom(evt)
        if not is_controlroom:
            return

        dms = []
        rooms = []
        unaliased_rooms = []
        controlroom = []

        joined_rooms = await self.plugin.client.get_joined_rooms()

        for room_id in joined_rooms:
            canonical_alias = await self._get_canonical_alias(room_id)
            if canonical_alias:
                rooms.append(f"* {canonical_alias} - {room_id}{NL}")
            else:
                dm_user = await self._is_direct_chat(room_id)
                if dm_user:
                    dms.append(f"* {dm_user} - {room_id}{NL}")
                else:
                    members = await self.plugin.client.get_joined_members(room_id)
                    if len(members) == 1 and self.plugin.client.mxid in members:
                        # this is a room that the bot is in by itself. so lonely :(
                        # so just leave the room.
                        await self.plugin.client.leave_room(room_id)
                    else:
                        if room_id == self.plugin.config["controlroom"]:
                            controlroom.append(f"* {room_id}{NL}")
                        else:
                            unaliased_rooms.append(
                                f"* {room_id} - {list(members.keys())} users{NL}"
                            )

        response = ""
        if rooms:
            response = response + f"##### Rooms{NL}{''.join(sorted(rooms))}"
        if dms:
            response = response + f"##### Direct Chats{NL}{''.join(sorted(dms))}"
        if unaliased_rooms:
            response = response + f"##### Unaliased Chats{NL}{''.join(sorted(unaliased_rooms))}"
        if controlroom:
            response = response + f"##### The Control Room{NL}{''.join(sorted(controlroom))}"

        await evt.respond(response)

    @admin.subcommand(help="Leave a Room")
    @command.argument("room_id", pass_raw=True)
    async def leave(self, evt: MessageEvent, room_id: str) -> None:
        is_controlroom = self._is_controlroom(evt)

        if not is_controlroom:
            return

        roomtoleave = self._get_first_mxid_link(evt)
        roomalias = ""

        if not roomtoleave:
            roomtoleave = room_id.split()[0]

        if roomtoleave[0] == "#" or roomtoleave[0] == "@":
            alias = await self.plugin.client.resolve_room_alias(roomtoleave)
            roomalias = roomtoleave
            roomtoleave = alias.room_id

        if roomtoleave[0] == "!":
            try:
                roomalias = await self._get_canonical_alias(roomtoleave)
            except MForbidden as e:
                await evt.respond(str(e))
                return

        joined_rooms = await self.plugin.client.get_joined_rooms()
        if roomtoleave not in joined_rooms:
            await evt.respond(f"I am not in the room {roomalias} ({roomtoleave})")
            return
        try:
            await self.plugin.client.leave_room(roomtoleave)
            await evt.respond(f"left room {roomalias} ({roomtoleave})")
        except (MUnknown, MForbidden) as e:
            await evt.respond(f"Can not leave room {roomalias} `{roomtoleave}`: {e}")
            return

    @admin.subcommand(help="Join a Room")
    @command.argument("room_id_or_alias", pass_raw=True)
    async def join(self, evt: MessageEvent, room_id_or_alias: str) -> None:
        is_controlroom = self._is_controlroom(evt)
        if not is_controlroom:
            return

        roomtojoin = self._get_first_mxid_link(evt)

        if not roomtojoin:
            roomtojoin = room_id_or_alias.split()[0]

        try:
            await self.plugin.client.join_room(roomtojoin, max_retries=0)
            await evt.respond(f"Joined room: {roomtojoin}")
        except (MUnknown, MForbidden) as e:
            await evt.respond(f"Unable to join room: {e}")

    @admin.subcommand(help="Send a message to a room")
    @command.argument("room_id", required=True)
    @command.argument("text", pass_raw=True, required=True)
    async def send_message(self, evt: MessageEvent, room_id: str, text: str) -> None:
        is_controlroom = self._is_controlroom(evt)
        if is_controlroom:
            if not room_id or not text:
                await evt.reply("need a room Id and a message")
            else:
                await self.plugin.client.send_text(room_id, text)
                await evt.reply(f"sent message to {room_id}")
