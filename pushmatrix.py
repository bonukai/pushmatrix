#!/usr/bin/python3

import argparse
import asyncio
import base64
import getpass
import jsonschema
import os
import pathlib
import sys

import aiohttp
from aiohttp import web
from aiohttp.web_request import Request

from nio import (
    AsyncClient,
    AsyncClientConfig,
    ErrorResponse,
    JoinedMembersError,
    JoinError,
    ProfileSetAvatarError,
    RoomCreateError,
    RoomCreateError,
    RoomInviteError,
    RoomVisibility,
    UploadResponse
)
from nio.responses import LoginError, ProfileGetAvatarResponse

from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("."),
    autoescape=select_autoescape()
)

template = env.get_template("index.html")


def exisiting_dir(path):
    if os.path.isdir(path) and os.path.exists(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a directory")


parser = argparse.ArgumentParser()

parser.add_argument(
    "--homeserver",
    help="Homeserver",
    default=os.environ.get("HOMESERVER") or "https://matrix-client.matrix.org",
    type=str
)

parser.add_argument(
    "--user-id",
    help="Username",
    required=os.environ.get("USER_ID") == None,
    default=os.environ.get("USER_ID"),
    type=str
)

parser.add_argument(
    "--password",
    help="Password",
    default=os.environ.get("PASSWORD"),
    type=str
)

parser.add_argument(
    "--store-dir",
    help="Store directory",
    default=os.environ.get("STORE_DIR") or "./store",
    type=exisiting_dir
)

parser.add_argument(
    "--receipients",
    help="Receipients",
    nargs="+",
    default=(os.environ.get("RECEIPIENTS") or "").split(" "),
    required=os.environ.get("RECEIPIENTS") == None,
    type=str,
)

parser.add_argument(
    "--room-name",
    help="Room name",
    default=os.environ.get("ROOM_NAME") or "pushmatrix",
    type=str
)


parser.add_argument(
    "--displayname",
    help="Display name",
    default=os.environ.get("DISPLAYNAME") or "pushmatrix",
    type=str
)

parser.add_argument(
    "--port",
    help="HTTP Port",
    default=8571,
    type=int
)

parser.add_argument(
    "--device-name",
    help="Device name",
    default=os.environ.get("DEVICE_NAME") or "pushmatrix",
    type=str,
)


parser.add_argument(
    "--app-token",
    help="pushmatrix token for authentication",
    default=os.environ.get("APP_TOKEN"),
    type=str,
)

parser.add_argument(
    "--message-type",
    choices=["notice", "text"],
    default=os.environ.get("MESSAGE_TYPE") or "text"
)

parser.add_argument(
    "--new-user-for-title",
    help="Register new user for every message's title",
    action="store_true",
    default=os.environ.get("NEW_USER_FOR_TITLE")
)

parser.add_argument(
    "--user-prefix",
    help="Prefix for new users. Use only with --new-user-for-title",
    default=os.environ.get("USER_PREFIX") or "pushmatrix_",
    type=str,
)

parser.add_argument(
    "--avatars-dir",
    help="Avatars directory. Use only with --new-user-for-title",
    default=os.environ.get("AVATARS_DIR") or "./avatars",
    type=exisiting_dir
)

args = parser.parse_args()

PASSWORD: str = args.password

if not PASSWORD:
    PASSWORD = getpass.getpass()

HOMESERVER: str = args.homeserver
USER_ID: str = args.user_id
DISPLAYNAME: str = args.displayname
RECEIPIENTS: list[str] = args.receipients
STORE_DIR: str = args.store_dir
ROOM_NAME: str = args.room_name
PORT: int = args.port
NEW_USER_FOR_TITLE: bool = args.new_user_for_title
USER_PREFIX: str = args.user_prefix
DEVICE_NAME: str = args.device_name
MESSAGE_TYPE: str = args.message_type
AVATARS_DIR: str = args.avatars_dir
APP_TOKEN: str = args.app_token

clientConfig = AsyncClientConfig(
    max_limit_exceeded=0,
    max_timeouts=0,
    store_sync_tokens=True,
    encryption_enabled=True,
)

mainClient = AsyncClient(
    homeserver=HOMESERVER,
    user=USER_ID,
    store_path=STORE_DIR,
    config=clientConfig
)

app = web.Application()

roomId: str = None
clients: dict[str, AsyncClient] = {}


async def inviteUserToRoom(newClient: AsyncClient):
    res = await mainClient.room_invite(
        room_id=roomId,
        user_id=newClient.user_id
    )

    if isinstance(res, RoomInviteError):
        raise Exception(res)

    await newClient.sync(timeout=3000, full_state=True)

    res = await newClient.join(roomId)

    if isinstance(res, JoinError):
        raise Exception(res)

    await newClient.sync(timeout=3000, full_state=True)


async def handleMessage(request: Request):
    schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "title": {"type": "string"},
        },
        "additionalProperties": False,
        "required": ["message", "title"]
    }

    if APP_TOKEN:
        schema["properties"]["token"] = {"type": "string"}
        schema["required"].append("token")

    data = await request.json()

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        return web.Response(status=400, text=e.message)

    message = data.get("message")
    title = data.get("title")
    token = data.get("token")

    if APP_TOKEN and token != APP_TOKEN:
        return web.Response(status=401, body="Invalid token")

    if NEW_USER_FOR_TITLE:
        newClient = await getClient(title)

        if not roomId in newClient.rooms.keys():
            await inviteUserToRoom(newClient)

        res = await newClient.room_send(
            room_id=roomId,
            content={
                "msgtype": f"m.{MESSAGE_TYPE}",
                "body": message,
            },
            message_type="m.room.message",
            ignore_unverified_devices=True
        )

        if isinstance(res, ErrorResponse):
            raise Exception(res)

        print(f"[{title}]: {message}")

    else:
        res = await mainClient.room_send(
            room_id=roomId,
            content={
                "msgtype": f"m.{MESSAGE_TYPE}",
                "body": f"{title}: {message}",
                "format": "org.matrix.custom.html",
                "formatted_body": f"<strong>{title}:</strong> {message}",
            },
            message_type="m.room.message",
            ignore_unverified_devices=True
        )

        if isinstance(res, ErrorResponse):
            raise Exception(res)

        print(f"[{DISPLAYNAME}]: {message}")

    return web.Response(body="Ok")


async def getMain(request: Request):
    body = template.render(token=(APP_TOKEN != None))

    return web.Response(
        body=body,
        content_type="text/html"
    )

app.add_routes([
    web.get("/", getMain),
    web.post("/message", handleMessage),
])


async def createRoom():
    res = await mainClient.room_create(
        visibility=RoomVisibility.private,
        name=ROOM_NAME,
        invite=RECEIPIENTS,
        initial_state=[{
            "type": "m.room.encryption",
                    "state_key": "",
                    "content": {
                        "algorithm": "m.megolm.v1.aes-sha2"
                    }
        },
            {
            "type": "m.room.power_levels",
                    "state_key": "",
                    "content": {
                        "ban": 0,
                        "invite": 0,
                        "kick": 0,
                        "redact": 0,
                        "users_default": 0,
                        "users": {
                            mainClient.user_id: 100
                        },
                        "events": {
                            "m.room.message": 50,
                            "m.room.avatar": 0,
                            "m.room.canonical_alias": 0,
                            "m.room.topic": 0,
                            "m.room.history_visibility": 0,
                        },
                    }
        }]
    )

    if isinstance(res, RoomCreateError):
        raise Exception(res)

    await mainClient.sync(full_state=True)

    return res.room_id


def findRoomId():
    room = next(
        (x for x in list(mainClient.rooms.values()) if x.name == ROOM_NAME),
        None
    )

    if room:
        return room.room_id


async def setAvatar(client: AsyncClient, path: pathlib.Path):
    res = await client.get_avatar()

    if isinstance(res, ProfileGetAvatarResponse):
        avatarUrl = await client.mxc_to_http(res.avatar_url)

        async with aiohttp.ClientSession() as session:
            async with session.get(avatarUrl) as res:
                if res.status == 200:

                    currentAvatarBytes = await res.read()
                    newAvatarBytes = pathlib.Path(path).read_bytes()

                    if currentAvatarBytes == newAvatarBytes:
                        return

    fileStat = path.stat()

    with open(str(path), "r+b") as f:
        print(f'Seeting avatar for user "{path.stem}"')

        res, _ = await client.upload(
            f,
            content_type=f"image/{path.suffix[1:]}",
            filesize=fileStat.st_size,
        )

        if isinstance(res, UploadResponse):
            res = await client.set_avatar(res.content_uri)

            if isinstance(res, ProfileSetAvatarError):
                print("Failed to set avatar")

        else:
            print(f'Failed to upload file: {path}')


def findAvatar(username: str):
    for path in pathlib.Path(AVATARS_DIR).iterdir():
        if not path.is_file():
            continue

        if len(path.suffix) <= 1:
            continue

        if path.stem == username:
            return path


async def getClient(title: str):
    userId = USER_PREFIX + base64.b64encode(title.encode()).decode().strip()

    newClient = clients.get(userId)

    if newClient:
        await newClient.sync(full_state=True)
        return newClient

    newClient = AsyncClient(
        homeserver=HOMESERVER,
        user=userId,
        store_path=STORE_DIR,
        config=clientConfig
    )

    print(f"Login in with: {userId} on server: {HOMESERVER}")

    res = await newClient.login(
        password=PASSWORD,
        device_name=DEVICE_NAME
    )

    if isinstance(res, LoginError):
        print(f"Failed. {res}")
        print("Trying to register")

        res = await newClient.register(
            username=userId,
            password=PASSWORD,
            device_name=DEVICE_NAME
        )

        if isinstance(res, ErrorResponse):
            raise Exception(res)

        await newClient.set_displayname(title)

    res_displayname = await newClient.get_displayname()
    if res_displayname.displayname.startswith(USER_PREFIX):
        print(f"Setting displayname for user {userId}")
        await newClient.set_displayname(title)

    if newClient.should_upload_keys:
        await newClient.keys_upload()

    if newClient.should_query_keys:
        await newClient.keys_query()

    if newClient.should_claim_keys:
        await newClient.keys_claim()

    await newClient.sync(full_state=True)

    avatarPath = findAvatar(title)

    if avatarPath:
        await setAvatar(newClient, avatarPath)

    clients[userId] = newClient

    return newClient


async def init():
    global roomId

    print(f"Login in with: {USER_ID} on server: {HOMESERVER}")

    res = await mainClient.login(
        password=PASSWORD,
        device_name=DEVICE_NAME
    )

    if isinstance(res, LoginError):
        print(f"Failed. {res}")
        print("Trying to register")

        res = await mainClient.register(
            username=USER_ID,
            password=PASSWORD,
            device_name=DEVICE_NAME
        )

        if isinstance(res, ErrorResponse):
            raise Exception(res)

    if mainClient.should_upload_keys:
        await mainClient.keys_upload()

    if mainClient.should_query_keys:
        await mainClient.keys_query()

    if mainClient.should_claim_keys:
        await mainClient.keys_claim()

    await mainClient.sync(full_state=True)
    await mainClient.set_displayname(DISPLAYNAME)

    roomId = findRoomId()

    if not roomId:
        roomId = await createRoom()

    else:
        members = await mainClient.joined_members(roomId)

        if isinstance(members, JoinedMembersError):
            raise Exception(members)

        membersId = map(lambda member: member.user_id, members.members)

        for receipient in RECEIPIENTS:
            if receipient not in membersId:
                res = await mainClient.room_invite(roomId, receipient)
                if isinstance(res, RoomInviteError):
                    raise Exception(res)

    if mainClient.should_upload_keys:
        await mainClient.keys_upload()

    if mainClient.should_query_keys:
        await mainClient.keys_query()

    if mainClient.should_claim_keys:
        await mainClient.keys_claim()

    avatarPath = findAvatar(DISPLAYNAME)

    if avatarPath:
        await setAvatar(mainClient, avatarPath)


def closeClients(client: AsyncClient):
    if client.logged_in:
        asyncio.run(client.logout())

    asyncio.run(client.close())

    for client in clients:
        if client.logged_in:
            asyncio.run(client.logout())

        asyncio.run(client.close())


def main():
    asyncio.get_event_loop().run_until_complete(init())

    asyncio.get_event_loop().create_task(
        mainClient.sync_forever(
            timeout=3000,
            full_state=True,
        )
    )

    web.run_app(app, port=PORT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Received keyboard interrupt.")
    finally:
        print("Exiting")
        closeClients(mainClient)
