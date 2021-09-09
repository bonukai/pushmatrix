FROM python:3-alpine AS builder

RUN apk update
RUN apk add --no-cache gcc olm-dev libffi-dev musl-dev

WORKDIR /app
COPY requirements.txt ./
RUN pip3 install --user --no-cache-dir -r requirements.txt

FROM python:3-alpine

RUN apk add --no-cache olm

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local:$PATH

COPY pushmatrix.py ./

ENV STORE_DIR "/store"
ENV AVATARS_DIR "/avatars"

VOLUME [ "/store", "/avatars" ]
EXPOSE 8571

CMD [ "python", "-u", "pushmatrix.py" ]