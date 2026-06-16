interface Props {
  title: string
  value: string | number
}

export default function DashboardCard(
  props: Props
) {

  return (
    <div className="rounded-xl border p-4">

      <div className="text-sm text-gray-500">
        {props.title}
      </div>

      <div className="text-2xl font-bold">
        {props.value}
      </div>

    </div>
  )
}