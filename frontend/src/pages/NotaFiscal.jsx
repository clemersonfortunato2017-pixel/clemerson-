// Template DANFE — Fortunato Auto Parts
// Gerado a partir do modelo original NF-e nº 180

export function renderDANFE(nf) {
  const {
    numero = '', serie = '1', chave = '', protocolo = '', protocoloData = '',
    emitente = {}, destinatario = {}, produtos = [], totais = {},
    transporte = {}, infoComplementar = '', natureza = 'Venda de Mercadoria',
  } = nf

  const fmt = (v) => Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })

  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<title>DANFE NF-e Nº ${numero} — ${emitente.nome || 'FORTUNATO AUTO PARTS LTDA'}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: Arial, sans-serif; font-size: 8pt; color: #000; background: #fff; }
  .danfe { width: 210mm; margin: 0 auto; padding: 4mm; }
  table { width: 100%; border-collapse: collapse; }
  td, th { border: 1px solid #000; padding: 1.5mm 2mm; vertical-align: top; }
  .label { font-size: 6pt; color: #333; display: block; }
  .value { font-size: 8pt; font-weight: bold; }
  .value-sm { font-size: 7pt; }
  .center { text-align: center; }
  .right { text-align: right; }
  .no-border { border: none; }
  .title-box { font-size: 10pt; font-weight: bold; text-align: center; line-height: 1.4; }
  .danfe-title { font-size: 11pt; font-weight: bold; letter-spacing: 1px; }
  .chave { font-family: monospace; font-size: 7pt; letter-spacing: 1px; }
  .section-header { background: #eee; font-weight: bold; font-size: 7pt; padding: 1mm 2mm; border: 1px solid #000; border-bottom: none; }
  .produtos th { background: #f0f0f0; font-size: 6.5pt; text-align: center; }
  .barcode { font-family: monospace; font-size: 6pt; text-align: center; letter-spacing: 3px; }
  hr { border: none; border-top: 1px dashed #999; margin: 2mm 0; }
  .canhoto { border: 1px solid #000; padding: 2mm; margin-bottom: 3mm; }
  @media print { body { margin: 0; } .danfe { margin: 0; } }
</style>
</head>
<body>
<div class="danfe">

  <!-- CANHOTO -->
  <div class="canhoto">
    <table><tr>
      <td style="border:none; width:65%">
        <span class="label">RECEBEMOS DE ${emitente.nome || 'FORTUNATO AUTO PARTS LTDA'} CNPJ ${emitente.cnpj || '60.950.673/0001-34'} OS PRODUTOS CONSTANTES NA NOTA FISCAL INDICADA AO LADO.</span>
      </td>
      <td style="border:none; width:35%; text-align:right">
        <span class="label">NF-e</span>
        <span class="value" style="font-size:12pt">Nº ${numero}</span><br/>
        <span class="label">SÉRIE: ${serie}</span>
      </td>
    </tr></table>
    <table style="margin-top:2mm"><tr>
      <td style="width:40%; border:1px solid #000; min-height:8mm">
        <span class="label">DATA DE RECEBIMENTO</span>
      </td>
      <td style="border:1px solid #000; min-height:8mm">
        <span class="label">IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR</span>
      </td>
    </tr></table>
  </div>

  <!-- CABEÇALHO PRINCIPAL -->
  <table>
    <tr>
      <!-- Logo/Razão Social -->
      <td style="width:55%; border:1px solid #000; padding:2mm">
        <div style="font-size:12pt; font-weight:bold; margin-bottom:2mm">${emitente.nome || 'FORTUNATO AUTO PARTS LTDA'}</div>
        <div class="value-sm">${emitente.endereco || 'RUA PROFESSORA AUGUSTA RIBAS, 520 - Pinheirinho'}</div>
        <div class="value-sm">CEP: ${emitente.cep || '81880-210'} ${emitente.municipio || 'Curitiba'} - ${emitente.uf || 'PR'}</div>
        <div class="value-sm">FONE: ${emitente.fone || '(41) 9723-0771'}</div>
        <div style="margin-top:1mm"><span class="label">FOLHA</span> <span class="value-sm">1/1</span></div>
      </td>
      <!-- DANFE title box -->
      <td style="width:22%; border:1px solid #000; padding:2mm; vertical-align:middle">
        <div class="title-box">
          <div class="danfe-title">DANFE</div>
          <div style="font-size:8pt; margin-top:2mm">DOCUMENTO AUXILIAR<br/>DE NOTA FISCAL<br/>ELETRÔNICA</div>
          <div style="margin-top:3mm; font-size:7pt">
            <span style="border:1px solid #000; padding:1mm 2mm">1</span>
            <span style="font-size:6pt; margin-left:1mm">0 - ENTRADA<br/>1 - SAÍDA</span>
          </div>
          <div style="margin-top:2mm">
            <span class="label">Nº</span> <span class="value" style="font-size:12pt">${numero}</span><br/>
            <span class="label">SÉRIE: ${serie}</span>
          </div>
        </div>
      </td>
      <!-- Chave de acesso -->
      <td style="width:23%; border:1px solid #000; padding:2mm">
        <span class="label">CHAVE DE ACESSO</span>
        <div class="chave" style="margin-top:1mm; word-break:break-all; font-size:6.5pt">${chave || '41260360950673000134550010000001801991597537'}</div>
        <div style="margin-top:2mm; font-size:6pt">Consulta de autenticidade no portal nacional da NF-e<br/>www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora.</div>
        <div style="margin-top:2mm">
          <span class="label">PROTOCOLO DE AUTORIZAÇÃO DE USO</span>
          <div class="value-sm">${protocolo || '141260104297994'} ${protocoloData || '17/03/2026 23:22:11'}</div>
        </div>
      </td>
    </tr>
  </table>

  <!-- NATUREZA + IE + CNPJ -->
  <table>
    <tr>
      <td style="width:55%">
        <span class="label">NATUREZA DA OPERAÇÃO</span>
        <div class="value">${natureza}</div>
      </td>
      <td style="width:20%">
        <span class="label">INSCRIÇÃO ESTADUAL</span>
        <div class="value">${emitente.ie || '9114949148'}</div>
      </td>
      <td style="width:12%">
        <span class="label">INSCRIÇÃO ESTADUAL DE SUBST.</span>
        <div class="value"></div>
      </td>
      <td>
        <span class="label">CNPJ</span>
        <div class="value">${emitente.cnpj || '60.950.673/0001-34'}</div>
      </td>
    </tr>
  </table>

  <!-- DESTINATÁRIO -->
  <div class="section-header">DESTINATÁRIO / REMETENTE</div>
  <table>
    <tr>
      <td style="width:55%">
        <span class="label">NOME / RAZÃO SOCIAL</span>
        <div class="value">${destinatario.nome || ''}</div>
      </td>
      <td style="width:25%">
        <span class="label">CNPJ / CPF</span>
        <div class="value">${destinatario.cpf_cnpj || ''}</div>
      </td>
      <td>
        <span class="label">DATA E HORA DA EMISSÃO</span>
        <div class="value">${nf.dataEmissao || ''}</div>
      </td>
    </tr>
    <tr>
      <td style="width:45%">
        <span class="label">ENDEREÇO</span>
        <div class="value">${destinatario.endereco || ''}</div>
      </td>
      <td style="width:20%">
        <span class="label">BAIRRO / DISTRITO</span>
        <div class="value">${destinatario.bairro || ''}</div>
      </td>
      <td style="width:15%">
        <span class="label">CEP</span>
        <div class="value">${destinatario.cep || ''}</div>
      </td>
      <td>
        <span class="label">DATA ENTRADA / SAÍDA</span>
        <div class="value">${nf.dataSaida || ''}</div>
      </td>
    </tr>
    <tr>
      <td>
        <span class="label">MUNICÍPIO</span>
        <div class="value">${destinatario.municipio || ''}</div>
      </td>
      <td>
        <span class="label">FONE / FAX</span>
        <div class="value">${destinatario.fone || ''}</div>
      </td>
      <td>
        <span class="label">UF</span>
        <div class="value">${destinatario.uf || ''}</div>
      </td>
      <td>
        <span class="label">INSCRIÇÃO ESTADUAL</span>
        <div class="value">${destinatario.ie || 'ISENTO'}</div>
      </td>
    </tr>
  </table>

  <!-- CÁLCULO DO IMPOSTO -->
  <div class="section-header">CÁLCULO DO IMPOSTO</div>
  <table>
    <tr>
      <td><span class="label">BASE DE CÁLCULO DO ICMS</span><div class="value right">R$ ${fmt(totais.baseIcms)}</div></td>
      <td><span class="label">VALOR DO ICMS</span><div class="value right">R$ ${fmt(totais.valorIcms)}</div></td>
      <td><span class="label">BASE DE CÁLCULO DO ICMS SUBST.</span><div class="value right">R$ ${fmt(totais.baseIcmsSt)}</div></td>
      <td><span class="label">VALOR DO ICMS SUBST.</span><div class="value right">R$ ${fmt(totais.valorIcmsSt)}</div></td>
      <td><span class="label">VALOR TOTAL DOS PRODUTOS</span><div class="value right">R$ ${fmt(totais.totalProdutos)}</div></td>
    </tr>
    <tr>
      <td><span class="label">VALOR DO FRETE</span><div class="value right">R$ ${fmt(totais.frete)}</div></td>
      <td><span class="label">VALOR DO SEGURO</span><div class="value right">R$ ${fmt(totais.seguro)}</div></td>
      <td><span class="label">DESCONTO</span><div class="value right">R$ ${fmt(totais.desconto)}</div></td>
      <td><span class="label">OUTRAS DESPESAS ACESSÓRIAS</span><div class="value right">R$ ${fmt(totais.outras)}</div></td>
      <td><span class="label">VALOR TOTAL DO IPI</span><div class="value right">R$ ${fmt(totais.ipi)}</div></td>
      <td><span class="label">VALOR TOTAL DA NOTA</span><div class="value right" style="font-size:10pt; font-weight:bold">R$ ${fmt(totais.totalNota)}</div></td>
    </tr>
  </table>

  <!-- TRANSPORTE -->
  <div class="section-header">TRANSPORTADOR / VOLUMES TRANSPORTADOS</div>
  <table>
    <tr>
      <td style="width:40%"><span class="label">NOME / RAZÃO SOCIAL</span><div class="value">${transporte.nome || ''}</div></td>
      <td><span class="label">FRETE POR CONTA</span><div class="value">${transporte.freteConta || '9-SEM FRETE'}</div></td>
      <td><span class="label">CÓDIGO ANTT</span><div class="value"></div></td>
      <td><span class="label">PLACA DO VEÍCULO</span><div class="value">${transporte.placa || ''}</div></td>
      <td><span class="label">UF</span><div class="value"></div></td>
      <td><span class="label">CNPJ / CPF</span><div class="value"></div></td>
    </tr>
    <tr>
      <td colspan="2"><span class="label">ENDEREÇO</span></td>
      <td colspan="2"><span class="label">MUNICÍPIO</span></td>
      <td><span class="label">UF</span></td>
      <td><span class="label">INSCRIÇÃO ESTADUAL</span></td>
    </tr>
    <tr>
      <td><span class="label">QUANTIDADE</span><div class="value">${transporte.quantidade || '0'}</div></td>
      <td><span class="label">ESPÉCIE</span></td>
      <td><span class="label">MARCA</span></td>
      <td><span class="label">NUMERAÇÃO</span></td>
      <td><span class="label">PESO BRUTO</span></td>
      <td><span class="label">PESO LÍQUIDO</span></td>
    </tr>
  </table>

  <!-- PRODUTOS -->
  <div class="section-header">DADOS DOS PRODUTOS / SERVIÇOS</div>
  <table class="produtos">
    <thead>
      <tr>
        <th style="width:5%">CÓDIGO</th>
        <th style="width:28%">DESCRIÇÃO DOS PRODUTOS / SERVIÇOS</th>
        <th style="width:8%">NCM/SH</th>
        <th style="width:6%">CST / CSOSN</th>
        <th style="width:5%">CFOP</th>
        <th style="width:4%">UNID</th>
        <th style="width:6%">QUANT.</th>
        <th style="width:8%">VALOR UNITÁRIO</th>
        <th style="width:8%">VALOR TOTAL</th>
        <th style="width:7%">BASE DE CÁLCULO ICMS</th>
        <th style="width:5%">VALOR IPI</th>
        <th style="width:5%">ALÍQUOTA ICMS %</th>
        <th style="width:5%">IPI %</th>
      </tr>
    </thead>
    <tbody>
      ${(produtos || []).map(p => `
      <tr>
        <td class="center">${p.codigo || ''}</td>
        <td>${p.descricao || ''}</td>
        <td class="center">${p.ncm || ''}</td>
        <td class="center">${p.cst || '0102'}</td>
        <td class="center">${p.cfop || '5102'}</td>
        <td class="center">${p.unidade || 'UN'}</td>
        <td class="right">${Number(p.quantidade || 1).toFixed(4)}</td>
        <td class="right">${fmt(p.valorUnitario)}</td>
        <td class="right">${fmt(p.valorTotal)}</td>
        <td class="right">0,00</td>
        <td class="right">0,00</td>
        <td class="right">0,00</td>
        <td class="right">0,00</td>
      </tr>`).join('')}
    </tbody>
  </table>

  <!-- ISSQN -->
  <div class="section-header">CÁLCULO DO ISSQN</div>
  <table>
    <tr>
      <td><span class="label">INSCRIÇÃO MUNICIPAL</span></td>
      <td><span class="label">VALOR TOTAL DOS SERVIÇOS</span></td>
      <td><span class="label">BASE DE CÁLCULO DO ISSQN</span></td>
      <td><span class="label">VALOR DO ISSQN</span></td>
    </tr>
  </table>

  <!-- DADOS ADICIONAIS -->
  <div class="section-header">DADOS ADICIONAIS</div>
  <table>
    <tr>
      <td style="width:70%; min-height:15mm">
        <span class="label">INFORMAÇÕES COMPLEMENTARES</span>
        <div class="value-sm" style="margin-top:1mm">${infoComplementar || ''}</div>
      </td>
      <td>
        <span class="label">RESERVADO AO FISCO</span>
      </td>
    </tr>
  </table>

</div>
</body>
</html>`
}

// Exemplo de uso — NF-e nº 180 (modelo original)
export const exemploNF180 = {
  numero: '180',
  serie: '1',
  chave: '41260360950673000134550010000001801991597537',
  protocolo: '141260104297994',
  protocoloData: '17/03/2026 23:22:11',
  dataEmissao: '17/03/2026 23:17:00',
  dataSaida: '17/03/2026',
  natureza: 'Venda de Mercadoria',
  emitente: {
    nome: 'FORTUNATO AUTO PARTS LTDA',
    cnpj: '60.950.673/0001-34',
    ie: '9114949148',
    endereco: 'RUA PROFESSORA AUGUSTA RIBAS, 520 - Pinheirinho',
    cep: '81880-210',
    municipio: 'Curitiba',
    uf: 'PR',
    fone: '(41) 9723-0771',
  },
  destinatario: {
    nome: 'VITOR FARIAS',
    cpf_cnpj: '138.609.739-08',
    endereco: 'Rua Francisco Saturnino dAndrade, 91',
    bairro: 'Sitio Cercado',
    cep: '81920-375',
    municipio: 'Curitiba',
    uf: 'PR',
    fone: '(99) 9999-9999',
    ie: 'ISENTO',
  },
  produtos: [
    { codigo: '2', descricao: 'BLOCO MOTOR ASTRA CHEVROLET PARCIAL', ncm: '84099912', cst: '0102', cfop: '5102', unidade: 'UN', quantidade: 1, valorUnitario: 4000.00, valorTotal: 4000.00 },
    { codigo: '37', descricao: 'BOBINA DE IGNIÇÃO', ncm: '85113020', cst: '0102', cfop: '5102', unidade: 'UN', quantidade: 1, valorUnitario: 450.00, valorTotal: 450.00 },
  ],
  totais: {
    baseIcms: 0, valorIcms: 0, baseIcmsSt: 0, valorIcmsSt: 0,
    totalProdutos: 4450.00, frete: 0, seguro: 0, desconto: 0,
    outras: 0, ipi: 0, totalNota: 4450.00,
  },
  transporte: { freteConta: '9-SEM FRETE', quantidade: 0 },
  infoComplementar: 'VALOR APROX DOS TRIBUTOS. FED: R$ 668,68; EST: R$ 801,00; MUN: R$ 0,00. BLOCO MOTOR 2.0 CHEVROLET 2001 PARCIAL COMPLETO NUMERO * NK0033315 *',
}
