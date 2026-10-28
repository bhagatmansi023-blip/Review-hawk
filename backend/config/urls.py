"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from reviews.api_views import (
    DashboardStatsView,
    PullRequestDetailView,
    PullRequestListView,
    ReviewDetailView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/auth/", include("repos.auth_urls")),
    path("api/webhook/", include("reviews.urls")),
    path("api/repos/", include("repos.urls")),
    # Top-level PR and review endpoints
    path("api/pull-requests/", PullRequestListView.as_view(), name="pull-requests-list"),
    path("api/pull-requests/<int:pk>/", PullRequestDetailView.as_view(), name="pull-requests-detail"),
    path("api/reviews/<int:pk>/", ReviewDetailView.as_view(), name="review-detail"),
    # Dashboard command center metrics
    path("api/dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
]