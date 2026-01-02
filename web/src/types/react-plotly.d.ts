declare module 'react-plotly.js' {
    import * as React from 'react';
    import * as Plotly from 'plotly.js';
    interface PlotlyEditorProps {
        data: Plotly.Data[];
        layout?: Partial<Plotly.Layout>;
        config?: Partial<Plotly.Config>;
        style?: React.CSSProperties;
        useResizeHandler?: boolean;
        className?: string;
        onClick?: (event: any) => void;
    }
    export default class Plot extends React.Component<PlotlyEditorProps> {}
}