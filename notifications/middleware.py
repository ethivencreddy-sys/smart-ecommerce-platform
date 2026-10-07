from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from jose import jwt, JWTError

from payment_api.auth import SECRET_KEY, ALGORITHM


@database_sync_to_async
def get_user(user_id):
    from django.contrib.auth.models import User

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        from django.contrib.auth.models import AnonymousUser
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        token = query_params.get("token", [None])[0]
        print("WEBSOCKET TOKEN RECEIVED:", bool(token))
        scope["user"] = AnonymousUser()

        if token:
            try:
                payload = jwt.decode(
                    token,
                    SECRET_KEY,
                    algorithms=[ALGORITHM]
                )

                user_id = payload.get("sub")

                if user_id:
                    scope["user"] = await get_user(user_id)

            except JWTError:
                scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)