"""Sabit hata formatı: {"error": {"code": "...", "message": "..."}}"""

import logging

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    MethodNotAllowed,
    NotFound,
    ParseError,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class ApiError(APIException):
    def __init__(self, code, message, status_code=status.HTTP_400_BAD_REQUEST):
        super().__init__(detail=message, code=code)
        self.code = code
        self.message = message
        self.status_code = status_code


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Beklenmeyen API hatası", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Beklenmeyen bir hata oluştu."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    extra = {}
    if isinstance(exc, ApiError):
        code, message = exc.code, exc.message
    elif isinstance(exc, Throttled):
        wait = int(exc.wait) + 1 if exc.wait else 1
        code = "rate_limited"
        message = f"Çok fazla istek gönderdiniz. {wait} saniye sonra tekrar deneyin."
    elif isinstance(exc, ValidationError):
        code, message = "validation_error", "Gönderilen veriler geçersiz."
        extra["details"] = response.data
    elif isinstance(exc, NotFound | Http404):
        code, message = "not_found", "Kaynak bulunamadı."
    elif isinstance(exc, MethodNotAllowed):
        code, message = "method_not_allowed", "Bu metot desteklenmiyor."
    elif isinstance(exc, ParseError):
        code, message = "invalid_json", "İstek gövdesi okunamadı."
    else:
        code = getattr(exc, "default_code", "error")
        message = str(getattr(exc, "detail", "Hata."))

    response.data = {"error": {"code": code, "message": message, **extra}}
    return response
