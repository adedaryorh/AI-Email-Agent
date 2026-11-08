import secrets
from app.repositories.oauth_repo import OAuthRepository

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import Cipher
from app.integrations.gmail import oauth
from app.integrations.gmail.client import GmailClient, GmailGateway
from app.models.mailbox import Mailbox
from app.repositories.mailbox_repo import MailboxRepository

STATE_MAX_AGE_SECONDS = 600


class MailboxService:
    def __init__(
        self, db: Session, mailboxes: MailboxRepository, cipher: Cipher, settings: Settings
    ):
        self.db = db
        self.mailboxes = mailboxes
        self.cipher = cipher
        self.settings = settings
        self.states = OAuthRepository(db)
        self._clients = {}
        self._signer = URLSafeTimedSerializer(settings.secret_key, salt="oauth-state")

    def list(self) -> list[Mailbox]:
        return self.mailboxes.list()

    def build_connect_url(self) -> str:
        nonce = secrets.token_urlsafe(32)
        self.states.issue(nonce, STATE_MAX_AGE_SECONDS)
        self.db.commit()
        state = self._signer.dumps({"nonce": nonce})
        return oauth.build_auth_url(
            client_id=self.settings.google_client_id,
            redirect_uri=self.settings.google_redirect_uri,
            state=state,
        )

    def connect_gmail(self, *, code: str, state: str) -> Mailbox:
        try:
            payload = self._signer.loads(state, max_age=STATE_MAX_AGE_SECONDS)
        except BadSignature as exc:
            raise AppError("Invalid or expired OAuth state") from exc

        if not self.states.consume(payload.get("nonce", "")):
            self.db.rollback()
            raise AppError("OAuth state already used or expired")
        self.db.commit()
        tokens = oauth.exchange_code(
            code=code,
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            redirect_uri=self.settings.google_redirect_uri,
        )
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise AppError("Google did not return a refresh token; revoke access and retry")

        client = GmailClient(lambda: tokens["access_token"])
        try:
            profile = client.get_profile()
        finally:
            client.close()
        email = profile["emailAddress"]

        mailbox = self.mailboxes.get_by_email(email)
        encrypted = self.cipher.encrypt(refresh_token)
        if mailbox:
            mailbox.encrypted_refresh_token = encrypted
        else:
            mailbox = self.mailboxes.add(
                Mailbox(email=email, provider="gmail", encrypted_refresh_token=encrypted)
            )
        self.db.commit()
        return mailbox

    def gmail_for(self, mailbox: Mailbox) -> GmailGateway:
        if mailbox.id in self._clients:
            return self._clients[mailbox.id]
        provider = oauth.TokenProvider(
            refresh_token=self.cipher.decrypt(mailbox.encrypted_refresh_token),
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
        )
        client = GmailClient(provider)
        self._clients[mailbox.id] = client
        return client

    def close(self):
        for client in self._clients.values():
            client.close()
        self._clients.clear()
