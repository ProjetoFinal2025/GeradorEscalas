# Projeto/core/forms.py

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from django.contrib import admin
from .models import Militar, Servico , Escala, EscalaMilitar

# Modifica a forma como Militar é exposto na view administrador
class MilitarForm(forms.ModelForm):
    class Meta:
        model = Militar
        fields = '__all__'
        exclude =  ['user']
        widgets = {
            'nim': forms.TextInput(attrs={
                'style': 'width: 200px;',
                'inputmode': 'numeric',
                'pattern': '[0-9]*',
            }),
            'user': forms.Select(attrs={'style': 'width: 200px;'}),
        }


# Modifica a forma como Serviço e exposto na view Admin

class ServicoForm(forms.ModelForm):
    # Mantém FilteredSelectMultiple para exibir os militares
    militares = forms.ModelMultipleChoiceField(
        queryset=Militar.objects.all(),
        widget=FilteredSelectMultiple("Militares", is_stacked=False),
        required=False
    )

    class Meta:
        model = Servico
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class EscalaForm(forms.ModelForm):
    e_escala_b = forms.ChoiceField(
        label="Tipo de Escala",
        choices=[("0", "Escala A"), ("1", "Escala B")],
        widget=forms.RadioSelect,
        required=True,
    )

    class Meta:
        model  = Escala
        fields = ["servico", "data", "e_escala_b", "observacoes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ─── Determina o serviço (POST ou instance) ──────────────────────
        servico = None
        has_errors = self.errors and len(self.errors) > 0  # Check if form has errors

        if not has_errors:  # Only modify widget if there are no validation errors
            if "servico" in self.data:
                try:
                    servico = Servico.objects.get(pk=self.data["servico"])
                except Servico.DoesNotExist:
                    pass
            elif self.instance and self.instance.pk:
                servico = self.instance.servico

            # ─── Ajusta o campo consoante o serviço ──────────────────────────
            if servico:
                if servico.tipo_escalas == "A":
                    # bloqueia em A
                    self.fields["e_escala_b"].widget = forms.HiddenInput()
                    self.initial["e_escala_b"] = "0"
                elif servico.tipo_escalas == "B":
                    # bloqueia em B
                    self.fields["e_escala_b"].widget = forms.HiddenInput()
                    self.initial["e_escala_b"] = "1"
                # para "AB" mantemos o radio-button

    # converte "0"/"1" → bool
    def clean_e_escala_b(self):
        return self.cleaned_data["e_escala_b"] == "1"


class EscalaMilitarForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.escala_id:
            servico_id = self.instance.escala.servico_id
            # Filter only Militares who are in that Servico
            self.fields['militar'].queryset = Militar.objects.filter(servicos__id=servico_id)

class EscalaMilitarInline(admin.TabularInline):
    model = EscalaMilitar
    form = EscalaMilitarForm