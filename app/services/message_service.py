from app.core.exceptions import NotFoundError

class MessageService:
    def __init__(self, repository):
        self.repository = repository

    def get(self, message_id):
        message = self.repository.get(message_id)
        if not message:
            raise NotFoundError(f"Message {message_id} not found")
        return message

    def list(self, **kwargs):
        return self.repository.list(**kwargs)
