interface Props {
  title: string
  value: string | number
}

export default function StatusCard({
  title,
  value
}: Props) {
  return (
    <div className="rounded-xl border p-4">
      <div className="text-sm text-gray-500">
        {title}
      </div>

      <div className="text-2xl font-bold">
        {value}
      </div>
    </div>
  )
}