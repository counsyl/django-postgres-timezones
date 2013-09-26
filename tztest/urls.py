from django.conf.urls import patterns, url


urlpatterns = patterns(
    '',

    url(r'^$', 'tztest.tztest.views.home', name='home'),
)
