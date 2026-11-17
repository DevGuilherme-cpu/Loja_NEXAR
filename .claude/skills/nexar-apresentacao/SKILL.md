---
name: nexar-apresentacao
description: Checklist e roteiro para a apresentação de 10 minutos da NEXAR (19/11/2026) — preparar banco, admin, internet, demo do CRUD e do 3D, e o que cada um fala. Usar quando pedirem para preparar, ensaiar ou revisar a apresentação.
---

# Apresentação da NEXAR (10 min)

## Véspera

- [ ] `python manage.py test loja` passando no MySQL local.
- [ ] MySQL ligado (Workbench, porta 3307) com o banco `nexar` e dados (`popular_loja` já rodado).
- [ ] Superusuário criado e testado em `/admin/` (o painel exige login de admin).
- [ ] Abrir todas as páginas uma vez (aquece o cache; o tênis .glb tem 7.8 MB).
- [ ] Site publicado na Vercel abrindo, se for mostrar o link.
- [ ] Internet: só a fonte vem de fora; levar o celular como roteador de reserva.
- [ ] Navegador Chrome atualizado (a transição card → produto usa View Transitions).
- [ ] Consultas SQL prontas numa aba do Workbench (seção 7 do plano em PDF).

## Roteiro

| Tempo | O que mostrar | Quem |
|---|---|---|
| 1 min | Problema e empresa: loja online onde o cliente gira a peça antes de comprar | Guilherme |
| 2 min | Home (peças caindo), loja com busca e filtro, foto trocando no hover, produto: foto vira 3D, tamanho muda a peça | Guilherme |
| 2 min | Diagrama ER: categorias → produtos → pedidos ← usuários; PK, FK, PROTECT | Eliton |
| 3 min | CRUD ao vivo no painel: cadastrar, buscar, editar (cor pinta o 3D), excluir; conferir no Workbench | Eliton |
| 1 min | JOIN: tela de pedidos + a mesma consulta no Workbench | Eliton |
| 1 min | Como o site fala com o banco: navegador → view do Django → SQL → MySQL → template | Os dois |

## Perguntas prováveis (respostas curtas)

- *Por que Django e não Flask?* Organização em apps, login e proteção CSRF prontos, ORM; o professor aprovou.
- *Onde está o SQL?* `sqlmigrate` mostra o CREATE TABLE; `.query` mostra o SELECT com JOIN; Workbench roda os comandos.
- *Quantas tabelas?* 4 nossas (auth_user, categorias, produtos, pedidos); as `django_*` são do framework.
- *Como o 3D funciona?* Three.js no navegador; peça gerada pelo contorno da roupa ou modelo .glb; a cor vem do banco.

## Plano B

- Sem internet: tudo do site é local; só a fonte cai para a do sistema.
- 3D travar: as fotos continuam (botões de foto na página do produto).
- MySQL não subir: mostrar o site publicado (Supabase) e o `banco.sql`.
