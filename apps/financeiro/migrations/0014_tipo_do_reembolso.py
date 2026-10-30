from django.db import migrations, models


class Migration(migrations.Migration):
    """O tipo (parcial ou integral) entra no conteúdo que a chave de idempotência identifica
    (E10-R01). Não há dados de produção (fase 1): as linhas de desenvolvimento ficam `parcial`."""

    dependencies = [
        ("financeiro", "0013_confirmacao_excepcional"),
    ]

    operations = [
        migrations.AddField(
            model_name="reembolso",
            name="tipo",
            field=models.CharField(
                choices=[("parcial", "Parcial"), ("integral", "Integral")],
                default="parcial",
                max_length=10,
            ),
            preserve_default=False,
        ),
    ]
