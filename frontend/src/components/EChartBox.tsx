import * as echarts from "echarts";
import { useEffect, useRef } from "react";

interface EChartBoxProps {
  option: echarts.EChartsOption;
  height?: number;
  ariaLabel?: string;
}

export function EChartBox({ option, height = 300, ariaLabel }: EChartBoxProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = echarts.init(el);
    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      chart.resize();
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setOption(option, true);
    }
  }, [option]);

  return (
    <div
      ref={containerRef}
      style={{ height: `${height}px`, width: "100%" }}
      role="img"
      aria-label={ariaLabel || "Financial analytics chart"}
    />
  );
}
