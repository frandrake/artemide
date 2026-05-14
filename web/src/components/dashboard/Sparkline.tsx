import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import './Sparkline.css';

export interface SparklineProps {
  data: number[];
  accent?: boolean;
  width?: number;
  height?: number;
  ariaLabel?: string;
}

export function Sparkline({
  data, accent = false, width = 60, height = 20, ariaLabel,
}: SparklineProps) {
  const series = data.map((v, i) => ({ i, v }));
  const stroke = accent ? 'var(--vermillion)' : 'var(--slate-blue)';
  const isEmpty = series.every((p) => p.v === 0);
  return (
    <span
      className="sparkline"
      role="img"
      aria-label={ariaLabel ?? (isEmpty ? 'No recent contact' : 'Contact frequency')}
      style={{ width, height }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={[0, 'dataMax']} />
          <Line
            type="monotone"
            dataKey="v"
            stroke={stroke}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </span>
  );
}

export default Sparkline;
