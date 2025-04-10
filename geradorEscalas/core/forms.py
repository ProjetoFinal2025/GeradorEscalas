# geradorEscalas/core/forms.py

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from .models import Militar, Servico

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
    militares = forms.ModelMultipleChoiceField(
        queryset=Militar.objects.all(),
        widget=FilteredSelectMultiple("Militares", is_stacked=False),
        required=False
    )

    class Meta:
        model = Servico
        fields = '__all__'
        exclude =  ['lista_militares']

    def __init__(self, *args, **kwargs):
        super(ServicoForm, self).__init__(*args, **kwargs)
        # Pré-preencher os militares se o objeto já existir
        if self.instance and self.instance.pk:
            nims = self.instance.lista_militares
            self.fields['militares'].initial = Militar.objects.filter(nim__in=nims)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Salvar apenas os NIMs dos militares selecionados
        instance.lista_militares = [m.nim for m in self.cleaned_data['militares']]
        if commit:
            instance.save()
        return instance
