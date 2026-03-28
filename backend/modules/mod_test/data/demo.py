# backend/modules/mod_test/data/demo.py
async def init_demo_data(env):
    print("   🎁 [DEMO] Inyectando datos relacionales en Laboratorio...")

    TestRecord = env['test.record']
    TestLine = env['test.line']

    existing = await TestRecord.search([])
    
    if not existing:
        print("      🧪 Generando cabecera y líneas de ensayo...")
        
        # 1. Creamos la Cabecera
        record = await TestRecord.create({
            'name': 'Experimento Relacional Alfa',
            'description': 'Validando el One2manyField y el Scaffolder',
            'status': 'draft'
        })
        
        # 2. Creamos las Líneas atadas al UUID de la cabecera
        await TestLine.create({
            'record_id': record.id,
            'name': 'Reactivo A',
            'qty': 15.5
        })
        
        await TestLine.create({
            'record_id': record.id,
            'name': 'Reactivo B',
            'qty': 7.0,
            'notes': 'Altamente volátil'
        })