from django.core.management.base import BaseCommand
from core.models import Categoria


class Command(BaseCommand):
    help = 'Precarga las categorías base predeterminadas globales del sistema en Finanza.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando precarga de categorías predeterminadas..."))

        categorias_base = [
            # ==============================
            # INGRESOS
            # ==============================
            {
                'nombre': 'Salario / Nómina',
                'tipo': 'INGRESO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Freelance / Servicios Profesionales',
                'tipo': 'INGRESO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Ventas y Negocio',
                'tipo': 'INGRESO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Inversiones y Rendimientos',
                'tipo': 'INGRESO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Bonos y Gratificaciones',
                'tipo': 'INGRESO',
                'clasificacion': 'IMPREVISTO',
                'padre': None,
            },
            {
                'nombre': 'Otros Ingresos',
                'tipo': 'INGRESO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },

            # ==============================
            # GASTOS FIJOS
            # ==============================
            {
                'nombre': 'Vivienda (Alquiler / Hipoteca)',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Servicios Básicos (Luz, Agua, Gas)',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Internet y Telefonía',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Suscripciones y Streaming',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Seguros (Médico, Auto, Hogar)',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Educación y Colegiaturas',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },
            {
                'nombre': 'Pago de Deudas y Préstamos',
                'tipo': 'GASTO',
                'clasificacion': 'FIJO',
                'padre': None,
            },

            # ==============================
            # GASTOS VARIABLES
            # ==============================
            {
                'nombre': 'Supermercado y Despensa',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Restaurantes y Cafeterías',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Transporte y Combustible',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Ropa y Calzado',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Salud, Cuidado Personal y Farmacia',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Entretenimiento y Ocio',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },
            {
                'nombre': 'Mascotas',
                'tipo': 'GASTO',
                'clasificacion': 'VARIABLE',
                'padre': None,
            },

            # ==============================
            # GASTOS IMPREVISTOS
            # ==============================
            {
                'nombre': 'Emergencias Médicas / Hospital',
                'tipo': 'GASTO',
                'clasificacion': 'IMPREVISTO',
                'padre': None,
            },
            {
                'nombre': 'Reparaciones del Hogar',
                'tipo': 'GASTO',
                'clasificacion': 'IMPREVISTO',
                'padre': None,
            },
            {
                'nombre': 'Reparación de Auto / Taller',
                'tipo': 'GASTO',
                'clasificacion': 'IMPREVISTO',
                'padre': None,
            },
            {
                'nombre': 'Multas y Trámites Urgentes',
                'tipo': 'GASTO',
                'clasificacion': 'IMPREVISTO',
                'padre': None,
            },
            {
                'nombre': 'Reemplazo de Dispositivos / Tecnología',
                'tipo': 'GASTO',
                'clasificacion': 'IMPREVISTO',
                'padre': None,
            },
        ]

        creadas = 0
        existentes = 0

        for item in categorias_base:
            categoria, created = Categoria.objects.get_or_create(
                usuario=None,
                nombre=item['nombre'],
                defaults={
                    'tipo': item['tipo'],
                    'clasificacion': item['clasificacion'],
                    'activa': True
                }
            )
            if created:
                creadas += 1
                self.stdout.write(self.style.SUCCESS(f"  + Creada: {categoria.nombre} [{categoria.tipo} - {categoria.clasificacion}]"))
            else:
                existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n¡Precarga finalizada con éxito! Total procesadas: {len(categorias_base)} (Nuevas: {creadas}, Ya existentes: {existentes})."
        ))
