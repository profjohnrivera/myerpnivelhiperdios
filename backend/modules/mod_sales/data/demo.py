# backend/modules/mod_sales/data/demo.py

async def init_demo_data(env):
    """
    🎁 INYECTOR DE DATOS DEMO (Nivel HiperDios)
    Genera registros automáticos con validación estricta de estados.
    """
    print("   🎁 [DEMO] Inyectando datos de prueba para Ventas y Contactos...")

    Partner = env['res.partner']
    SaleOrder = env['sale.order']
    Company = env['res.company']

    # 🏢 1. OBTENEMOS LA COMPAÑÍA
    companies = await Company.search([])
    if not companies:
        print("      ⚠️ No hay compañía base. Creando una por defecto...")
        company = await Company.create({'name': 'HiperDios Corp'})
        company_id = company.id
    else:
        company_id = companies[0].id

    # 👤 2. CREAMOS CLIENTES DEMO
    clientes = await Partner.search([])
    if not clientes:
        print("      👤 Generando Clientes Demo...")
        c1 = await Partner.create({'name': 'SpaceX Corp', 'email': 'elon@spacex.com', 'company_id': company_id})
        c2 = await Partner.create({'name': 'Stark Industries', 'email': 'tony@stark.com', 'company_id': company_id})
        c3 = await Partner.create({'name': 'Wayne Enterprises', 'email': 'bruce@wayne.com', 'company_id': company_id})
    else:
        c1 = clientes[0]
        c2 = clientes[1] if len(clientes) > 1 else clientes[0]

    # 🛒 3. CREAMOS PEDIDOS DE VENTA DEMO
    pedidos = await SaleOrder.search([])
    if not pedidos:
        print("      🛒 Generando Pedidos de Venta Demo...")
        
        await SaleOrder.create({
            'name': 'PED-2026-0001',
            'partner_id': c1.id,
            'company_id': company_id,
            'state': 'draft', # ✅ Válido
        })
        
        await SaleOrder.create({
            'name': 'PED-2026-0002',
            'partner_id': c2.id,
            'company_id': company_id,
            'state': 'sale', # 🔥 FIX: Estado corregido de 'confirmed' a 'sale'
        })