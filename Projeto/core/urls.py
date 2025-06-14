from django.urls import path
from django.views.generic import RedirectView, TemplateView
from django.contrib.auth.views import LogoutView, PasswordChangeView, PasswordChangeDoneView
from django.contrib import messages
from .views import (
    login_view, home_view, mapa_dispensas_view, escala_servico_view, 
    gerar_escalas_view, lista_servicos_view,
    previsoes_por_servico_view, previsoes_servico_view, exportar_previsoes_pdf, 
    exportar_escalas_pdf, obter_militar,
    obter_militares_disponiveis, substituir_militar, obter_nomeacao_atual,
    editar_observacao_nomeacao, previsualizar_previsoes_pdf,
    atualizar_ordem_militares
)


class CustomLogoutView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        messages.success(request, 'Sessão terminada com sucesso.')
        return super().dispatch(request, *args, **kwargs)

urlpatterns = [
    path('', RedirectView.as_view(url='login/', permanent=False)),
    path('login/', login_view, name='login'),
    path('logout/', CustomLogoutView.as_view(next_page='login'), name='logout'),
    path('home/', home_view, name='home'),
    path('guia/', TemplateView.as_view(template_name='admin/guia.html'), name='guia'),
    path('mapa-dispensas/', mapa_dispensas_view, name='mapa_dispensas'),
    path('escala-servico/', escala_servico_view, name='escala_servico'),
    path('escala-servico/<int:servico_id>/', escala_servico_view, name='escala_servico_detalhe'),
    path('gerar-escalas/', gerar_escalas_view, name='gerar_escalas'),
    path('servicos/', lista_servicos_view, name='lista_servicos'),
    path('previsoes-por-servico/', previsoes_por_servico_view, name='previsoes_por_servico'),
    path('previsoes-servico/<int:servico_id>/', previsoes_servico_view, name='previsoes_servico'),
    path('previsoes-servico/<int:servico_id>/previsualizar/', previsualizar_previsoes_pdf, name='previsualizar_previsoes_pdf'),
    path('previsoes-servico/<int:servico_id>/exportar/', exportar_previsoes_pdf, name='exportar_previsoes_pdf'),
    path('previsoes-servico/<int:servico_id>/exportar_pdf/', RedirectView.as_view(url='/previsoes-servico/%(servico_id)s/exportar/'), name='exportar_previsoes_pdf_old'),
    path('escala-servico/<int:servico_id>/exportar_pdf/', exportar_escalas_pdf, name='exportar_escalas_pdf'),
    path('alterar-senha/', PasswordChangeView.as_view(template_name='core/alterar_senha.html'), name='alterar_senha'),
    path('senha-alterada/', PasswordChangeDoneView.as_view(template_name='core/senha_alterada.html'), name='senha_alterada'),
    path('senha-alterada/', PasswordChangeDoneView.as_view(template_name='core/senha_alterada.html'), name='password_change_done'),
    path('api/militar/<str:militar_nim>/', obter_militar, name='obter_militar'),
    path('api/militares/disponiveis/<int:servico_id>/<str:data>/', obter_militares_disponiveis, name='obter_militares_disponiveis'),
    path('api/nomeacao/substituir/', substituir_militar, name='substituir_militar'),
    path('api/nomeacao/atual/<int:servico_id>/<str:data>/<str:tipo>/', obter_nomeacao_atual, name='obter_nomeacao_atual'),
    path('api/nomeacao/editar_observacao/', editar_observacao_nomeacao, name='editar_observacao_nomeacao'),
    path('escalas/<int:escala_id>/reordenar/', atualizar_ordem_militares, name='atualizar_ordem_militares'),
]
