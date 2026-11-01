from django.db import migrations

from apps.nucleo.so_insercao import instalar_protecao_so_insercao


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0007_apuracao_final'),
    ]

    operations = [
        instalar_protecao_so_insercao("pedidos_apuracaofinal"),
    ]
