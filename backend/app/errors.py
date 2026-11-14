"""User-facing analysis errors. Lives in its own module so stages can import it
without importing app.main (which imports the stages: that would be circular)."""


class AnalysisError(Exception):
    """Raise from any stage to return a clean error to the frontend.

    code:   invalid_musicxml | invalid_audio | no_voice_detected | internal_error
    stage:  score | pitch | segment | align | grade | feedback
    status: 400 bad input, 422 input fine but can't analyze, 500 our bug
    """

    def __init__(self, code: str, message: str, stage: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.stage, self.status = code, message, stage, status
