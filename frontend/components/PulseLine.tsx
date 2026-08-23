export default function PulseLine() {
  return (
    <svg
      viewBox="0 0 340 40"
      className="w-full h-8"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {/*
        Left half: jagged, irregular strokes — representing failed/erratic payments.
        Right half: settles into an even, steady beat — representing recovery.
        This is the page's one deliberate signature element.
      */}
      <path
        className="pulse-path"
        d="M0,20 L14,20 L20,6 L26,34 L32,12 L38,28 L44,20 L58,20
           L64,4 L70,32 L76,18 L82,20 L96,20
           L102,10 L108,26 L114,20 L128,20
           L140,20 L152,14 L164,20 L176,20
           L188,16 L200,20 L212,20
           L224,18 L236,20 L248,20
           L260,19 L272,20 L284,20
           L296,19.5 L308,20 L320,20 L340,20"
        fill="none"
        stroke="#7B3B49"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
