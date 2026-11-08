class RetentionService:
    def __init__(self, db, repository):
        self.db, self.repository = db, repository

    def purge(self, days):
        count = self.repository.purge(days)
        self.db.commit()
        return count
