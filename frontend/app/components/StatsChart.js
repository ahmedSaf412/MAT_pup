'use client';

import { useEffect, useRef } from 'react';
import { Chart, registerables } from 'chart.js';
import styles from './StatsChart.module.css';

Chart.register(...registerables);

// Shared dark theme defaults
const DARK_THEME = {
  color: 'rgba(255, 255, 255, 0.7)',
  borderColor: 'rgba(255, 255, 255, 0.1)',
};

export function LineChart({ data, title = 'Progress Over Time' }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    if (chartRef.current) chartRef.current.destroy();

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels: data?.labels || ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
        datasets: [
          {
            label: 'Score',
            data: data?.scores || [45, 55, 60, 72, 78, 85],
            borderColor: '#00D4FF',
            backgroundColor: 'rgba(0, 212, 255, 0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#00D4FF',
            pointBorderColor: '#FFFFFF',
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: title,
            color: DARK_THEME.color,
            font: { family: 'Outfit', size: 14, weight: 600 },
          },
        },
        scales: {
          x: {
            grid: { color: DARK_THEME.borderColor },
            ticks: { color: DARK_THEME.color, font: { size: 11 } },
          },
          y: {
            min: 0,
            max: 100,
            grid: { color: DARK_THEME.borderColor },
            ticks: { color: DARK_THEME.color, font: { size: 11 } },
          },
        },
      },
    });

    return () => chartRef.current?.destroy();
  }, [data, title]);

  return (
    <div className={styles.chartContainer}>
      <canvas ref={canvasRef} />
    </div>
  );
}

export function RadarChart({ data, title = 'Move Accuracy' }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    if (chartRef.current) chartRef.current.destroy();

    chartRef.current = new Chart(canvasRef.current, {
      type: 'radar',
      data: {
        labels: data?.labels || ['Front Kick', 'Roundhouse', 'Side Kick', 'Punch', 'Block', 'Stance'],
        datasets: [
          {
            label: 'Accuracy',
            data: data?.scores || [85, 72, 68, 90, 78, 82],
            backgroundColor: 'rgba(0, 212, 255, 0.15)',
            borderColor: '#00D4FF',
            borderWidth: 2,
            pointBackgroundColor: '#00D4FF',
            pointBorderColor: '#FFFFFF',
            pointBorderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: title,
            color: DARK_THEME.color,
            font: { family: 'Outfit', size: 14, weight: 600 },
          },
        },
        scales: {
          r: {
            grid: { color: DARK_THEME.borderColor },
            angleLines: { color: DARK_THEME.borderColor },
            pointLabels: { color: DARK_THEME.color, font: { size: 11 } },
            ticks: {
              display: false,
              stepSize: 20,
            },
            min: 0,
            max: 100,
          },
        },
      },
    });

    return () => chartRef.current?.destroy();
  }, [data, title]);

  return (
    <div className={styles.chartContainer}>
      <canvas ref={canvasRef} />
    </div>
  );
}
