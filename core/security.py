import os


def get_client_ip(request):
    """IP do cliente usado pelo django-axes para limitar tentativas de login.

    `X-Forwarded-For` pode ser forjado por quem acessa direto o servidor, então
    nunca é lido. Na Vercel, a plataforma sobrescreve `x-vercel-forwarded-for`
    com o IP real do cliente (um proxy na frente não o altera), e só nesse caso
    ele é confiável. Nos demais ambientes (Render, local) usamos `REMOTE_ADDR`.
    Atrás de um proxy sem esse cabeçalho confiável, `REMOTE_ADDR` é o IP do
    proxy: o bloqueio passa a valer por usuário, o que continua impedindo o
    ataque de força bruta.
    """
    if os.environ.get('VERCEL'):
        forwarded = request.META.get('HTTP_X_VERCEL_FORWARDED_FOR', '')
        client_ip = forwarded.split(',')[0].strip()
        if client_ip:
            return client_ip
    return request.META.get('REMOTE_ADDR', '')
