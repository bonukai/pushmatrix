# pushmatrix

Simple selfhosted REST API for sending end to end encrypted push notifications over [Matrix](https://matrix.org) protocol, build with [matrix-nio](https://github.com/poljar/matrix-nio).

It allows to send encrypted messages with simple HTTP request, that you can receive in any Matrix client, like [Element](https://element.io/get-started)

```bash
curl -X POST 127.0.0.1:8571/message \
   -H 'Content-Type: application/json' \
   -d '{"message":"Low disk space - 1 GB", "title":"system"}'
```
![screenshot](/screenshots/1.png) ![screenshot](/screenshots/2.png)

## Usage

### Start server

```bash
docker run -d \
	--name pushmatrix \
	-p 8571:8571 \
	-e USER_ID="@username:matrix.org" \
	-e PASSWORD="password" \
	-e RECEIPIENTS="@user1:matrix.org @user2:matrix.org @user3:matrix.org" \
	-e ROOM_NAME="pushmatrix" \
	-e APP_TOKEN="QOL4OO73EC1DEXE5A2N4" \
	bonukai/pushmatrix
```

or with docker compse

```yaml
# docker-compose.yaml
version: "3.7"
services:
  pushmatrix:
    name: pushmatrix
    image: bonukai/pushmatrix
      ports:
        - 8571:8571
      environment:
        USER_ID: "@username:matrix.org"
        PASSWORD: "password"
        RECEIPIENTS: "@user1:matrix.org @user2:matrix.org @user3:matrix.org"
        ROOM_NAME: "pushmatrix"
        APP_TOKEN: "QOL4OO73EC1DEXE5A2N4"
```

```bash
docker-compose up -d
```

If your homeserver supports registration without email adress and captcha, then you can receive notifications from different users for every title.

```bash
docker run -d \
	--name pushmatrix \
	-p 8571:8571 \
	-v ./avatars:/avatars:ro \
	-e USER_ID="@username:matrix.org" \
	-e PASSWORD="password" \
	-e RECEIPIENTS="@user1:matrix.org @user2:matrix.org @user3:matrix.org" \
	-e ROOM_NAME="pushmatrix" \
	-e APP_TOKEN="QOL4OO73EC1DEXE5A2N4" \
	-e NEW_USER_FOR_TITLE="yes" \
	bonukai/pushmatrix
```

### Authentication

Access to the API can be limited by providing APP_TOKEN environment variable

## API

### POST /message

**Data constraints**

```json
{
  "title": "[title]",
  "messgage": "[message]",
  "token": "[optional app token]"
}
```

**Data example**

```json
{
  "title": "System",
  "messgage": "Low disk space",
  "token": "QOL4OO73EC1DEXE5A2N4"
}
```

### Success Response

**Code** : `200 OK`

**Content example**

```
Ok
```