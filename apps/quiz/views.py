from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.throttling import ScopedRateThrottle

from .models import Category
from .serializers import CategorySerializer


@extend_schema(summary="Aktif kategorileri listeler", tags=["quiz"])
class CategoryListView(ListAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "read"
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    pagination_class = None
