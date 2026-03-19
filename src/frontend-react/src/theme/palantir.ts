import * as echarts from 'echarts';

export const PALANTIR_THEME = {
  color: [
    '#2d72d2', '#22c55e', '#ef4444', '#f59e0b', '#a78bfa',
    '#06b6d4', '#ec4899', '#ff6400', '#eab308', '#94a3b8',
  ],
  backgroundColor: '#1c2127',
  textStyle: {
    color: '#e2e8f0',
  },
  title: {
    textStyle: { color: '#e2e8f0' },
    subtextStyle: { color: '#94a3b8' },
  },
  legend: {
    textStyle: { color: '#94a3b8' },
  },
  tooltip: {
    backgroundColor: '#252a31',
    borderColor: '#394b59',
    textStyle: { color: '#e2e8f0' },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#394b59' } },
    axisTick: { lineStyle: { color: '#394b59' } },
    axisLabel: { color: '#94a3b8' },
    splitLine: { lineStyle: { color: '#252a31' } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: '#394b59' } },
    axisTick: { lineStyle: { color: '#394b59' } },
    axisLabel: { color: '#94a3b8' },
    splitLine: { lineStyle: { color: '#252a31' } },
  },
};

export function registerPalantirTheme() {
  echarts.registerTheme('palantir', PALANTIR_THEME);
}
