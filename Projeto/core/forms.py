# Projeto/core/forms.py

from django import forms
from django.forms import HiddenInput
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
                'maxlength': '8',
                'minlength': '8',
                'placeholder': '00000000',
            }),
            'user': forms.Select(attrs={'style': 'width: 200px;'}),
        }

    def clean_nim(self):
        nim = self.cleaned_data.get('nim')
        if nim:
            # Garante que o NIM tenha 8 dígitos preenchendo com zeros à esquerda
            nim = nim.zfill(8)
        return nim

# Modifica a forma como Serviço e exposto na view Admin

class MilitarComEscalasMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        escalas = obj.listar_escalas()
        return f"{obj.posto} {obj.nome} ({obj.nim}) - Escalas: {escalas}"

class ServicoForm(forms.ModelForm):
    # Mantém FilteredSelectMultiple para exibir os militares
    militares = MilitarComEscalasMultipleChoiceField(
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
        fields = ["servico", "e_escala_b", "observacoes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "servico" in self.fields:
            w = self.fields["servico"].widget
            w.can_add_related = False
            w.can_change_related = False
            w.can_view_related = False

        if self.instance and self.instance.pk:
            self.fields["e_escala_b"].widget = forms.HiddenInput()
            self.fields["e_escala_b"].required = False
            self.initial["e_escala_b"] = "1" if self.instance.e_escala_b else "0"
            return

        # — only reach this code on *add* or when there are validation errors —
        servico = None
        has_errors = bool(self.errors)  # True if form already has validation errors



        if not has_errors:
            if "servico" in self.data:
                try:
                    servico = Servico.objects.get(pk=self.data["servico"])
                except Servico.DoesNotExist:
                    pass
            elif self.instance and self.instance.pk:
                servico = self.instance.servico

            if servico:
                if servico.tipo_escalas == "A":
                    self.fields["e_escala_b"].widget = forms.HiddenInput()
                    self.initial["e_escala_b"] = "0"
                elif servico.tipo_escalas == "B":
                    self.fields["e_escala_b"].widget = forms.HiddenInput()
                    self.initial["e_escala_b"] = "1"
                # if tipo_escalas == "AB", leave the radio buttons up and required

    # converte
    def clean_e_escala_b(self):
        return self.cleaned_data["e_escala_b"] == "1"


class EscalaMilitarForm(forms.ModelForm):
    class Meta:
        model = EscalaMilitar
        fields = ['militar', 'ordem']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.escala_id:
            escala = self.instance.escala
            servico_id = escala.servico_id
            self.fields['militar'].queryset = Militar.objects.filter(servicos__id=servico_id)

            # Dynamically rename the field label
            self.fields['ordem'].label = "Ordem FDS" if escala.e_escala_b else "Ordem Semana"

class EscalaMilitarInline(admin.TabularInline):
    model = EscalaMilitar
    form = EscalaMilitarForm