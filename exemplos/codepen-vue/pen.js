// Painel JS do CodePen. Usa a API estática minuto-a-minuto (CORS liberado).
const { createApp } = Vue;

const API = "https://minutoaminuto.pages.dev";

const NOMES_UF = {
  AC: "Acre", AL: "Alagoas", AM: "Amazonas", AP: "Amapá", BA: "Bahia", CE: "Ceará",
  DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MG: "Minas Gerais",
  MS: "Mato Grosso do Sul", MT: "Mato Grosso", PA: "Pará", PB: "Paraíba", PE: "Pernambuco",
  PI: "Piauí", PR: "Paraná", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RO: "Rondônia",
  RR: "Roraima", RS: "Rio Grande do Sul", SC: "Santa Catarina", SE: "Sergipe", SP: "São Paulo",
  TO: "Tocantins", ZZ: "Exterior",
};

const REGIOES = {
  Norte: ["AC", "AM", "AP", "PA", "RO", "RR", "TO"],
  Nordeste: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
  "Centro-Oeste": ["DF", "GO", "MS", "MT"],
  Sudeste: ["ES", "MG", "RJ", "SP"],
  Sul: ["PR", "RS", "SC"],
  Exterior: ["ZZ"],
};

// Cores fixas pelo número do candidato, iguais em todas as eleições (13 = PT, 22 = PL).
// Os demais recebem cores na ordem do resultado final.
const CORES_FIXAS = { 13: "#0f766e", 22: "#ea580c" };
const CORES = ["#7c3aed", "#0284c7", "#be185d", "#65a30d", "#a16207", "#475569"];

// Último ponto de uma série até o instante t (as séries estão em ordem de t).
function pontoAte(pontos, t) {
  let lo = 0, hi = pontos.length - 1, achado = null;
  while (lo <= hi) {
    const m = (lo + hi) >> 1;
    if (pontos[m].t <= t) { achado = pontos[m]; lo = m + 1; } else { hi = m - 1; }
  }
  return achado;
}

createApp({
  data() {
    return {
      NOMES_UF,
      eleicoes: [],
      eleicaoId: "2022-2t",
      ufs: [],
      local: "BR",
      eixos: [
        { id: "minuto", nome: "Por horário" },
        { id: "pct", nome: "Por % apurado" },
      ],
      eixo: "minuto",
      series: {}, // { minuto, pct } do local escolhido
      seriesUf: {}, // série por minuto de cada UF, para o progresso por região
      indice: 0,
      linhas: [],
      tocando: false,
      velocidade: 5,
      timer: null,
      erro: "",
    };
  },
  computed: {
    base() {
      return `${API}/v1/eleicoes/${this.eleicaoId}/presidente/br`;
    },
    serie() {
      return this.series[this.eixo];
    },
    pontos() {
      return this.serie ? this.serie.pontos : [];
    },
    ponto() {
      return this.pontos[this.indice];
    },
    candidatos() {
      return this.serie ? this.serie.candidatos : [];
    },
    candidatosPorResultado() {
      // ordem do resultado final do local: define a ordem dos botões e as cores dos demais
      const final = this.pontos[this.pontos.length - 1];
      return [...this.candidatos].sort((a, b) => final.votos[b.numero] - final.votos[a.numero]);
    },
    validos() {
      return this.candidatos.reduce((s, c) => s + this.ponto.votos[c.numero], 0);
    },
    lideres() {
      // os dois mais votados no instante escolhido, o primeiro à esquerda;
      // empates (como antes do primeiro boletim) seguem a ordem do resultado final
      return [...this.candidatosPorResultado]
        .sort((a, b) => this.ponto.votos[b.numero] - this.ponto.votos[a.numero])
        .slice(0, 2);
    },
    outros() {
      if (!this.validos) return 0;
      const doisPrimeiros = this.lideres.reduce((s, c) => s + this.pctValidos(c.numero), 0);
      return Math.max(0, 100 - doisPrimeiros);
    },
    regioes() {
      if (!this.ponto) return [];
      return Object.entries(REGIOES).map(([nome, ufs]) => {
        let apuradas = 0, total = 0;
        for (const uf of ufs) {
          const pontos = this.seriesUf[uf];
          if (!pontos) continue;
          total += pontos[pontos.length - 1].secoes;
          apuradas += pontoAte(pontos, this.ponto.t)?.secoes ?? 0;
        }
        return { nome, pct: total ? (100 * apuradas) / total : 0 };
      });
    },
    faixa() {
      // faixa vertical ajustada às linhas visíveis (ignora o início instável, < 1% apurado)
      const valores = this.pontos
        .filter((p) => p.pct_secoes >= 1)
        .flatMap((p) => this.linhas.map((n) => this.pctValidosDe(p, n)));
      return { min: Math.floor(Math.min(50, ...valores) - 1), max: Math.ceil(Math.max(50, ...valores) + 1) };
    },
  },
  watch: {
    eleicaoId() {
      this.local = "BR";
      this.carregarEleicao();
    },
    local() {
      this.carregarLocal();
    },
  },
  async mounted() {
    const indice = await this.buscar(`${API}/v1/index.json`);
    if (!indice) return;
    this.eleicoes = indice.eleicoes;
    await this.carregarEleicao();
  },
  methods: {
    async buscar(url) {
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
      } catch (e) {
        this.erro = `Não foi possível carregar ${url}: ${e.message}`;
        return null;
      }
    },
    async carregarEleicao() {
      this.pausar();
      this.series = {};
      const resumo = await this.buscar(`${this.base}/resumo.json`);
      if (!resumo) return;
      // os links do resumo do Brasil listam as UFs disponíveis
      this.ufs = resumo._links.filhos.map((f) => f.name);
      const series = await Promise.all(
        this.ufs.map((uf) => this.buscar(`${this.base}/${uf.toLowerCase()}/serie-minuto.json`))
      );
      this.seriesUf = Object.fromEntries(this.ufs.map((uf, i) => [uf, series[i]?.pontos]));
      await this.carregarLocal();
      this.linhas = this.candidatosPorResultado.slice(0, 2).map((c) => c.numero);
    },
    async carregarLocal() {
      this.pausar();
      const base = this.local === "BR" ? this.base : `${this.base}/${this.local.toLowerCase()}`;
      const [minuto, pct] = await Promise.all([
        this.buscar(`${base}/serie-minuto.json`),
        this.buscar(`${base}/serie-pct.json`),
      ]);
      if (!minuto || !pct) return;
      this.series = { minuto, pct };
      this.indice = Math.min(this.indice, this.pontos.length - 1);
    },
    trocarEixo(eixo) {
      // mantém o mesmo % apurado ao trocar de eixo
      const pct = this.ponto ? this.ponto.pct_secoes : 0;
      this.eixo = eixo;
      const i = this.pontos.findIndex((p) => p.pct_secoes >= pct);
      this.indice = i === -1 ? this.pontos.length - 1 : i;
    },
    alternarLinha(numero) {
      this.linhas = this.linhas.includes(numero)
        ? this.linhas.filter((n) => n !== numero)
        : [...this.linhas, numero];
    },
    alternarPlay() {
      if (this.tocando) return this.pausar();
      if (this.indice >= this.pontos.length - 1) this.indice = 0;
      this.tocando = true;
      this.timer = setInterval(() => {
        if (this.indice >= this.pontos.length - 1) return this.pausar();
        this.indice = Math.min(this.indice + this.velocidade, this.pontos.length - 1);
      }, 100);
    },
    pausar() {
      this.tocando = false;
      clearInterval(this.timer);
    },
    cor(numero) {
      if (CORES_FIXAS[numero]) return CORES_FIXAS[numero];
      const demais = this.candidatosPorResultado.filter((c) => !CORES_FIXAS[c.numero]);
      const i = demais.findIndex((c) => c.numero === numero);
      return CORES[Math.min(i, CORES.length - 1)];
    },
    pctValidosDe(p, numero) {
      // % dos votos válidos: só votos nominais (sem brancos e nulos)
      const validos = this.candidatos.reduce((s, c) => s + p.votos[c.numero], 0);
      return validos ? (100 * p.votos[numero]) / validos : 0;
    },
    pctValidos(numero) {
      return this.pctValidosDe(this.ponto, numero);
    },
    linha(numero) {
      return this.pontos.map((p, i) => `${this.x(i)},${this.y(this.pctValidosDe(p, numero))}`).join(" ");
    },
    x(i) {
      return (600 * i) / Math.max(this.pontos.length - 1, 1);
    },
    y(pct) {
      const { min, max } = this.faixa;
      const limitado = Math.min(max, Math.max(min, pct ?? 50));
      return 180 - ((limitado - min) / (max - min)) * 180;
    },
    nomeEleicao(id) {
      const [ano, turno] = id.split("-");
      return `${turno[0]}º turno de ${ano}`;
    },
    hora(iso) {
      return iso.slice(11, 16);
    },
    fmtPct(v, casas = 2) {
      return `${v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
    },
    fmtNum(v) {
      return v.toLocaleString("pt-BR");
    },
  },
}).mount("#app");
