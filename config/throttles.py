"""Oturum (session_id) tabanlı hız sınırları.

IP başına sınırlar `X-Forwarded-For` zincirine (NUM_PROXIES) güvenir; bu sınırlar ise URL'deki
oturum kimliğine bağlıdır ve istemci başlıklarından etkilenmez. Meşru bir oyuncu oturum başına en
fazla 20 soru ve 20 cevap üretebilir, bu yüzden sınırlar normal kullanımın çok üstündedir.
"""

from rest_framework.throttling import SimpleRateThrottle


class SessionRateThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        session_id = view.kwargs.get("session_id")
        if session_id is None:
            return None
        # URL dönüştürücüsü UUID nesnesi verir: büyük/küçük harf varyantları aynı sayaca düşer.
        return self.cache_format % {"scope": self.scope, "ident": str(session_id)}


class AnswerSessionThrottle(SessionRateThrottle):
    scope = "answer_session"


class QuestionSessionThrottle(SessionRateThrottle):
    scope = "question_session"
