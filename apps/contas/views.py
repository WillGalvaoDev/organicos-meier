from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def inicio(request: HttpRequest) -> HttpResponse:
    """Página inicial autenticada: nome e papel, até as telas de cada papel existirem."""
    return render(request, "inicio.html", {"conta": request.user})
