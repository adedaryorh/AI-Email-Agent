class EnrichmentService:
    def __init__(self, db, assistant, audit):
        self.db, self.assistant, self.audit = db, assistant, audit

    def extract(self, message):
        if message.entities is None:
            message.entities = self.assistant.extract(message)
            self.audit.add(message.id, "entities_extracted", {"prompt_version": "v1"})
            self.db.commit()
        return message.entities
