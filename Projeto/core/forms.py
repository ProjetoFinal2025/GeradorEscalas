# Projeto/core/forms.py

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from .models import Militar, Servico , Escala

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
    class Meta:
        model = Escala
        fields = ['servico', 'data', 'e_escala_b', 'observacoes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)