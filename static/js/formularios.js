// Ajudas dos formulários (checkout, cadastro e login). Tudo também é validado no servidor.
(() => {
  const digitos = v => v.replace(/\D/g, '');

  // máscaras enquanto digita
  const MASCARAS = {
    cpf: v => digitos(v).slice(0, 11).replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2')
      .replace(/(\d{3})(\d{1,2})$/, '$1-$2'),
    telefone: v => {
      const d = digitos(v).slice(0, 11);
      if (d.length <= 2) return d;
      const meio = d.length > 10 ? 7 : 6;
      return `(${d.slice(0, 2)}) ${d.slice(2, meio)}${d.length > meio ? '-' + d.slice(meio) : ''}`;
    },
    cep: v => digitos(v).slice(0, 8).replace(/(\d{5})(\d)/, '$1-$2'),
  };
  document.querySelectorAll('[data-mascara]').forEach(campo => {
    const mascara = MASCARAS[campo.dataset.mascara];
    campo.addEventListener('input', () => { campo.value = mascara(campo.value); });
  });

  // mostrar/ocultar senha
  document.querySelectorAll('.ver-senha').forEach(b => b.addEventListener('click', () => {
    const campo = b.previousElementSibling;
    const mostrar = campo.type === 'password';
    campo.type = mostrar ? 'text' : 'password';
    b.textContent = mostrar ? 'Ocultar' : 'Mostrar';
    b.setAttribute('aria-pressed', String(mostrar));
    b.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
  }));

  // força da senha no cadastro (só orienta: quem decide é o validador do Django)
  const senha = document.querySelector('input[name="password1"]');
  const forca = document.getElementById('forca-senha');
  if (senha && forca) {
    const NIVEIS = ['Muito fraca', 'Fraca', 'Razoável', 'Boa', 'Forte'];
    senha.addEventListener('input', () => {
      const v = senha.value;
      const pontos = !v ? -1 : [v.length >= 8, v.length >= 12, /[a-z]/.test(v) && /[A-Z]/.test(v), /\d/.test(v),
        /[^A-Za-z0-9]/.test(v)].filter(Boolean).length - (v.length < 8 ? 1 : 0);
      const nivel = Math.max(0, Math.min(4, pontos));
      forca.dataset.nivel = v ? nivel : '';
      forca.querySelector('span').textContent = v ? NIVEIS[nivel] : '';
    });
  }

  const form = document.getElementById('checkout');
  if (!form) return;

  // frete e total do resumo mudam com a entrega escolhida (o servidor recalcula ao confirmar)
  const reais = n => n ? n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : 'Grátis';
  const atualizar = () => {
    const envio = form.querySelector('input[name="envio"]:checked')?.value || 'padrao';
    const frete = Number(form.dataset[envio === 'expresso' ? 'freteExpresso' : 'fretePadrao']);
    form.querySelector('[data-frete]').textContent = reais(frete);
    form.querySelector('[data-total]').textContent = reais(Number(form.dataset.subtotal) + frete);
  };
  form.querySelectorAll('input[name="envio"]').forEach(r => r.addEventListener('change', atualizar));
  atualizar();

  // CEP: preenche rua, bairro, cidade e estado pelo ViaCEP (precisa de internet; sem ela, digita-se à mão)
  const cep = form.elements.cep;
  const status = document.getElementById('cep-status');
  let ultimo = '';
  cep.addEventListener('input', async () => {
    const d = digitos(cep.value);
    if (d.length !== 8 || d === ultimo) return;
    ultimo = d;
    status.textContent = 'Buscando o endereço...';
    try {
      const r = await fetch(`https://viacep.com.br/ws/${d}/json/`);
      const dados = await r.json();
      if (dados.erro) { status.textContent = 'CEP não encontrado. Confira ou preencha o endereço.'; return; }
      form.elements.endereco.value = dados.logradouro || form.elements.endereco.value;
      form.elements.bairro.value = dados.bairro || form.elements.bairro.value;
      form.elements.cidade.value = dados.localidade || '';
      form.elements.uf.value = dados.uf || '';
      status.textContent = `Endereço encontrado: ${dados.localidade} (${dados.uf}).`;
      (dados.logradouro ? form.elements.numero : form.elements.endereco).focus();
    } catch {
      status.textContent = 'Sem conexão para buscar o CEP. Preencha o endereço normalmente.';
    }
  });
})();
