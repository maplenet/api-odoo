from fastapi import APIRouter, HTTPException
from app.core.sendgrid_email import send_email_sendgrid

router = APIRouter(prefix="/email", tags=["email"])

@router.post("/sendgrid")
async def test_sendgrid():
    """
    Endpoint para probar el envío de correo usando SendGrid con datos fijos.
    """
    # Datos de prueba (hardcodeados)
    to_email = "richard.guarachi.ticona@gmail.com"  # Cambia este correo por uno de prueba
    subject = "Prueba de correo con SendGrid"
    html_content = """
    <h1>Hola</h1>
    <p>Este es un correo de prueba enviado desde FastAPI utilizando SendGrid.</p>
    """

    try:
        response = send_email_sendgrid(to_email, subject, html_content)
        return {"detail": "Correo enviado exitosamente", "status_code": response.status_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {str(e)}")
