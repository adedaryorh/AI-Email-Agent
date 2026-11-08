class AnalyticsService:
    def __init__(self, repository):
        self.repository = repository

    def overview(self):
        return self.repository.overview()
