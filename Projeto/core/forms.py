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
    TIPO_ESCALA_CHOICES = [
        (False, 'Escala A'),
        (True, 'Escala B'),
    ]

    e_escala_b = forms.TypedChoiceField(
        choices=TIPO_ESCALA_CHOICES,
        coerce=lambda x: x == 'True',
        widget=forms.Select,
        label='Tipo de Escala'
    )

    class Meta:
        model = Escala
        fields = ['servico', 'data', 'e_escala_b', 'observacoes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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