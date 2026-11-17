from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repos', '0004_repository_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='html_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='pullrequest',
            name='html_url',
            field=models.URLField(blank=True, default=''),
        ),
    ]