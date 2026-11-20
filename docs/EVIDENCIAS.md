# Evidências de execução

Geradas automaticamente por `scripts/gerar_evidencias.py` em 20/11/2026 20:08, executando a API real contra um banco SQLite temporário.

Divergências em relação ao esperado: **0**

## Cenário 01 — Acesso indevido

Ana (Comercial) tenta consultar a solicitação de Bruno (Tecnologia).

**POST /reembolsos** — usuário: `bruno`

```json
{
  "categoria": "hospedagem",
  "valor": 999.9,
  "data_despesa": "2026-11-20",
  "justificativa": "Hospedagem em evento de tecnologia",
  "comprovante_ref": "NF-BRUNO-01"
}
```
Resposta: **HTTP 201**

```json
{
  "id": 1,
  "solicitante_id": 2,
  "solicitante_nome": "Bruno Lima",
  "departamento_id": 2,
  "categoria": "hospedagem",
  "valor": 999.9,
  "data_despesa": "2026-11-20",
  "justificativa": "Hospedagem em evento de tecnologia",
  "comprovante_ref": "NF-BRUNO-01",
  "situacao": "rascunho",
  "criado_em": "2026-11-20T23:08:55.054242Z",
  "atualizado_em": "2026-11-20T23:08:55.054263Z"
}
```

**GET /reembolsos/1** — usuário: `ana`

Resposta: **HTTP 404**

```json
{
  "detail": "Solicitação não encontrada."
}
```

**GET /reembolsos/987654** — usuário: `ana`

Resposta: **HTTP 404**

```json
{
  "detail": "Solicitação não encontrada."
}
```


## Cenário 02 — Gestor de outro departamento

Patrícia (gestora do Comercial) tenta aprovar despesa de Tecnologia.

**POST /reembolsos/1/enviar** — usuário: `bruno`

Resposta: **HTTP 200**

```json
{
  "id": 1,
  "solicitante_id": 2,
  "solicitante_nome": "Bruno Lima",
  "departamento_id": 2,
  "categoria": "hospedagem",
  "valor": 999.9,
  "data_despesa": "2026-11-20",
  "justificativa": "Hospedagem em evento de tecnologia",
  "comprovante_ref": "NF-BRUNO-01",
  "situacao": "aguardando_gestor",
  "criado_em": "2026-11-20T23:08:55.054242Z",
  "atualizado_em": "2026-11-20T23:08:55.103787Z"
}
```

**POST /reembolsos/1/gestor/aprovar** — usuário: `patricia`

Resposta: **HTTP 403**

```json
{
  "detail": "RN03: esta solicitação pertence a outro departamento; você não é o responsável por ela."
}
```

**GET /reembolsos/1/historico** — usuário: `bruno`

Resposta: **HTTP 200**

```json
[
  {
    "id": 1,
    "reembolso_id": 1,
    "responsavel_id": 2,
    "responsavel_nome": "Bruno Lima",
    "responsavel_perfil": "colaborador",
    "etapa": "submissao",
    "decisao": "enviada",
    "observacao": null,
    "data_hora": "2026-11-20T23:08:55.103960Z"
  }
]
```


## Cenário 03 — Credenciais incorretas

**POST /auth/login** — usuário: `sem token`

```json
{
  "email": "ana@nexuscorp.com",
  "senha": "********"
}
```
Resposta: **HTTP 401**

```json
{
  "detail": "Credenciais inválidas."
}
```

**POST /auth/login** — usuário: `sem token`

```json
{
  "email": "naoexiste@nexuscorp.com",
  "senha": "********"
}
```
Resposta: **HTTP 401**

```json
{
  "detail": "Credenciais inválidas."
}
```

**GET /reembolsos** — usuário: `sem token`

Resposta: **HTTP 401**

```json
{
  "detail": "Não autenticado: token ausente, inválido, expirado ou encerrado."
}
```


## Cenário 04 — Tentativa de alteração de permissões

**POST /auth/cadastro** — usuário: `sem token`

```json
{
  "nome": "Intruso Teste",
  "email": "intruso@nexuscorp.com",
  "senha": "********",
  "departamento_id": 1,
  "perfil": "financeiro"
}
```
Resposta: **HTTP 422**

```json
{
  "detail": [
    {
      "campo": "body.perfil",
      "mensagem": "Extra inputs are not permitted",
      "tipo": "extra_forbidden"
    }
  ]
}
```

**PATCH /usuarios/me** — usuário: `ana`

```json
{
  "perfil": "financeiro"
}
```
Resposta: **HTTP 422**

```json
{
  "detail": [
    {
      "campo": "body.perfil",
      "mensagem": "Extra inputs are not permitted",
      "tipo": "extra_forbidden"
    }
  ]
}
```

**PATCH /usuarios/me** — usuário: `ana`

```json
{
  "departamento_id": 3
}
```
Resposta: **HTTP 422**

```json
{
  "detail": [
    {
      "campo": "body.departamento_id",
      "mensagem": "Extra inputs are not permitted",
      "tipo": "extra_forbidden"
    }
  ]
}
```

**GET /usuarios/me** — usuário: `ana`

Resposta: **HTTP 200**

```json
{
  "id": 1,
  "nome": "Ana Souza",
  "email": "ana@nexuscorp.com",
  "perfil": "colaborador",
  "departamento_id": 1
}
```


## Cenário 05 — Aprovação fora da sequência

O financeiro (Carla) tenta aprovar uma solicitação que ainda aguarda o gestor.

**POST /reembolsos** — usuário: `ana`

```json
{
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01"
}
```
Resposta: **HTTP 201**

```json
{
  "id": 2,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01",
  "situacao": "rascunho",
  "criado_em": "2026-11-20T23:08:55.393485Z",
  "atualizado_em": "2026-11-20T23:08:55.393507Z"
}
```

**POST /reembolsos/2/enviar** — usuário: `ana`

Resposta: **HTTP 200**

```json
{
  "id": 2,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01",
  "situacao": "aguardando_gestor",
  "criado_em": "2026-11-20T23:08:55.393485Z",
  "atualizado_em": "2026-11-20T23:08:55.405643Z"
}
```

**POST /reembolsos/2/financeiro/aprovar** — usuário: `carla`

Resposta: **HTTP 409**

```json
{
  "detail": "Operação 'financeiro_aprovar' incompatível com a situação 'aguardando_gestor'. A solicitação ainda aguarda a análise do gestor (RN08)."
}
```


## Cenário 06 — Manipulação de solicitação

Após o envio, Ana tenta mudar o valor de R$ 180,00 para R$ 1.800,00.

**PATCH /reembolsos/2** — usuário: `ana`

```json
{
  "valor": 1800.0
}
```
Resposta: **HTTP 409**

```json
{
  "detail": "RN07: uma solicitação na situação 'aguardando_gestor' não pode ser alterada; isso só é possível enquanto ela estiver em rascunho."
}
```

**GET /reembolsos/2** — usuário: `ana`

Resposta: **HTTP 200**

```json
{
  "id": 2,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01",
  "situacao": "aguardando_gestor",
  "criado_em": "2026-11-20T23:08:55.393485Z",
  "atualizado_em": "2026-11-20T23:08:55.405643Z"
}
```


## Cenário 07 — Consulta com filtros

Patrícia consulta as pendentes do seu departamento; nada de Tecnologia aparece.

**POST /reembolsos** — usuário: `ana`

```json
{
  "categoria": "alimentacao",
  "valor": 60.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Almoço com cliente em visita externa",
  "comprovante_ref": "NF-ANA-02"
}
```
Resposta: **HTTP 201**

```json
{
  "id": 3,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "alimentacao",
  "valor": 60.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Almoço com cliente em visita externa",
  "comprovante_ref": "NF-ANA-02",
  "situacao": "rascunho",
  "criado_em": "2026-11-20T23:08:55.433397Z",
  "atualizado_em": "2026-11-20T23:08:55.433417Z"
}
```

**GET /reembolsos?situacao=aguardando_gestor** — usuário: `patricia`

Resposta: **HTTP 200**

```json
[
  {
    "id": 2,
    "solicitante_id": 1,
    "solicitante_nome": "Ana Souza",
    "departamento_id": 1,
    "categoria": "transporte",
    "valor": 180.0,
    "data_despesa": "2026-11-20",
    "justificativa": "Táxi para reunião com cliente",
    "comprovante_ref": "NF-ANA-01",
    "situacao": "aguardando_gestor",
    "criado_em": "2026-11-20T23:08:55.393485Z",
    "atualizado_em": "2026-11-20T23:08:55.405643Z"
  }
]
```

**GET /reembolsos?situacao=aguardando_gestor&categoria=transporte** — usuário: `patricia`

Resposta: **HTTP 200**

```json
[
  {
    "id": 2,
    "solicitante_id": 1,
    "solicitante_nome": "Ana Souza",
    "departamento_id": 1,
    "categoria": "transporte",
    "valor": 180.0,
    "data_despesa": "2026-11-20",
    "justificativa": "Táxi para reunião com cliente",
    "comprovante_ref": "NF-ANA-01",
    "situacao": "aguardando_gestor",
    "criado_em": "2026-11-20T23:08:55.393485Z",
    "atualizado_em": "2026-11-20T23:08:55.405643Z"
  }
]
```

**GET /reembolsos?departamento_id=2** — usuário: `patricia`

Resposta: **HTTP 200**

```json
[]
```


## Cenário 08 — Histórico financeiro

Aprovação do gestor, aprovação do financeiro e pagamento, com todos os responsáveis.

**POST /reembolsos/2/gestor/aprovar** — usuário: `patricia`

```json
{
  "observacao": "Conferido com o cliente"
}
```
Resposta: **HTTP 200**

```json
{
  "id": 2,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01",
  "situacao": "aguardando_financeiro",
  "criado_em": "2026-11-20T23:08:55.393485Z",
  "atualizado_em": "2026-11-20T23:08:55.467049Z"
}
```

**POST /reembolsos/2/financeiro/aprovar** — usuário: `carla`

```json
{
  "observacao": "Valor dentro da política"
}
```
Resposta: **HTTP 200**

```json
{
  "id": 2,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01",
  "situacao": "aprovada",
  "criado_em": "2026-11-20T23:08:55.393485Z",
  "atualizado_em": "2026-11-20T23:08:55.479307Z"
}
```

**POST /reembolsos/2/financeiro/pagar** — usuário: `carla`

```json
{
  "observacao": "Pagamento registrado"
}
```
Resposta: **HTTP 200**

```json
{
  "id": 2,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "transporte",
  "valor": 180.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Táxi para reunião com cliente",
  "comprovante_ref": "NF-ANA-01",
  "situacao": "paga",
  "criado_em": "2026-11-20T23:08:55.393485Z",
  "atualizado_em": "2026-11-20T23:08:55.494122Z"
}
```

**GET /reembolsos/2/historico** — usuário: `ana`

Resposta: **HTTP 200**

```json
[
  {
    "id": 2,
    "reembolso_id": 2,
    "responsavel_id": 1,
    "responsavel_nome": "Ana Souza",
    "responsavel_perfil": "colaborador",
    "etapa": "submissao",
    "decisao": "enviada",
    "observacao": null,
    "data_hora": "2026-11-20T23:08:55.405789Z"
  },
  {
    "id": 3,
    "reembolso_id": 2,
    "responsavel_id": 3,
    "responsavel_nome": "Patrícia Alves",
    "responsavel_perfil": "gestor",
    "etapa": "gestor",
    "decisao": "aprovada",
    "observacao": "Conferido com o cliente",
    "data_hora": "2026-11-20T23:08:55.467171Z"
  },
  {
    "id": 4,
    "reembolso_id": 2,
    "responsavel_id": 6,
    "responsavel_nome": "Carla Mendes",
    "responsavel_perfil": "financeiro",
    "etapa": "financeiro",
    "decisao": "aprovada",
    "observacao": "Valor dentro da política",
    "data_hora": "2026-11-20T23:08:55.479440Z"
  },
  {
    "id": 5,
    "reembolso_id": 2,
    "responsavel_id": 6,
    "responsavel_nome": "Carla Mendes",
    "responsavel_perfil": "financeiro",
    "etapa": "pagamento",
    "decisao": "paga",
    "observacao": "Pagamento registrado",
    "data_hora": "2026-11-20T23:08:55.494270Z"
  }
]
```

**PATCH /reembolsos/2** — usuário: `ana`

```json
{
  "valor": 5
}
```
Resposta: **HTTP 409**

```json
{
  "detail": "RN07: uma solicitação na situação 'paga' não pode ser alterada; isso só é possível enquanto ela estiver em rascunho. Solicitações encerradas são imutáveis."
}
```


## Extra — Recusa exige justificativa (RN11) e logout encerra o token (RN14)

**POST /reembolsos** — usuário: `ana`

```json
{
  "categoria": "materiais",
  "valor": 75.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Material de escritório para o cliente",
  "comprovante_ref": "NF-ANA-03"
}
```
Resposta: **HTTP 201**

```json
{
  "id": 4,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "materiais",
  "valor": 75.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Material de escritório para o cliente",
  "comprovante_ref": "NF-ANA-03",
  "situacao": "rascunho",
  "criado_em": "2026-11-20T23:08:55.524074Z",
  "atualizado_em": "2026-11-20T23:08:55.524094Z"
}
```

**POST /reembolsos/4/enviar** — usuário: `ana`

Resposta: **HTTP 200**

```json
{
  "id": 4,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "materiais",
  "valor": 75.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Material de escritório para o cliente",
  "comprovante_ref": "NF-ANA-03",
  "situacao": "aguardando_gestor",
  "criado_em": "2026-11-20T23:08:55.524074Z",
  "atualizado_em": "2026-11-20T23:08:55.538587Z"
}
```

**POST /reembolsos/4/gestor/recusar** — usuário: `patricia`

```json
{}
```
Resposta: **HTTP 422**

```json
{
  "detail": [
    {
      "campo": "body.observacao",
      "mensagem": "Field required",
      "tipo": "missing"
    }
  ]
}
```

**POST /reembolsos/4/gestor/recusar** — usuário: `patricia`

```json
{
  "observacao": "Despesa sem relação com o serviço prestado"
}
```
Resposta: **HTTP 200**

```json
{
  "id": 4,
  "solicitante_id": 1,
  "solicitante_nome": "Ana Souza",
  "departamento_id": 1,
  "categoria": "materiais",
  "valor": 75.0,
  "data_despesa": "2026-11-20",
  "justificativa": "Material de escritório para o cliente",
  "comprovante_ref": "NF-ANA-03",
  "situacao": "recusada",
  "criado_em": "2026-11-20T23:08:55.524074Z",
  "atualizado_em": "2026-11-20T23:08:55.559266Z"
}
```

**POST /auth/logout** — usuário: `ana`

Resposta: **HTTP 204**

```json
(sem corpo)
```

**GET /reembolsos** — usuário: `ana`

Resposta: **HTTP 401**

```json
{
  "detail": "Não autenticado: token ausente, inválido, expirado ou encerrado."
}
```

