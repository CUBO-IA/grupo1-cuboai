import uuid

from django.db import migrations, models


def fill_public_ids(apps, schema_editor):
    for name in ("DogProfile", "Quote"):
        model = apps.get_model("tienda", name)
        for obj in model.objects.all():
            obj.public_id = uuid.uuid4()
            obj.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [("tienda", "0002_quote_pricing")]

    operations = [
        migrations.AddField(
            model_name="dogprofile",
            name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.AddField(
            model_name="quote",
            name="public_id",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(fill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="dogprofile",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
        migrations.AlterField(
            model_name="quote",
            name="public_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
