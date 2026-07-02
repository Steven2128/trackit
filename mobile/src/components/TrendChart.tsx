import { Dimensions } from "react-native";
import { BarChart } from "react-native-chart-kit";

import { colors } from "../theme/colors";

type Props = {
  months: string[];
  totals: number[];
};

const chartConfig = {
  backgroundGradientFrom: colors.surface,
  backgroundGradientTo: colors.surface,
  decimalPlaces: 0,
  color: (opacity = 1) => `rgba(91, 141, 239, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(163, 168, 179, ${opacity})`,
  propsForBackgroundLines: { stroke: colors.border },
  barPercentage: 0.6,
};

const MES_ABREV = [
  "ene","feb","mar","abr","may","jun",
  "jul","ago","sep","oct","nov","dic",
];

function labelOf(yyyymm: string): string {
  const m = Number(yyyymm.split("-")[1]);
  return MES_ABREV[m - 1] ?? yyyymm;
}

export default function TrendChart({ months, totals }: Props) {
  const width = Dimensions.get("window").width - 32;
  return (
    <BarChart
      data={{
        labels: months.map(labelOf),
        datasets: [{ data: totals.length > 0 ? totals : [0] }],
      }}
      width={width}
      height={200}
      chartConfig={chartConfig}
      fromZero
      showValuesOnTopOfBars={false}
      withInnerLines
      yAxisLabel=""
      yAxisSuffix=""
      style={{ borderRadius: 12 }}
    />
  );
}
