from django.shortcuts import render

from tztest.tztest.main import generate_test_table


def home(request):
    table = generate_test_table()
    no_header = request.GET.get('noheader', False)
    return render(request, 'tztest/index.html',
                  {'table': table, 'no_header': no_header})
