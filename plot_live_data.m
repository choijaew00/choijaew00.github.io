% plot_live_data.m (메모리 크래시 및 창 꺼짐 완전 해결 버전)
function [img_bytes, w, h] = plot_live_data(time_strings, temperatures, humidities)
    t_str = string(time_strings);
    data_len = length(temperatures);

    % 1. 가상 도화지 인스턴스 확인
    fig = findobj('Type', 'figure', 'Name', 'THM_ENGINE');
    if isempty(fig)
        fig = figure('Name', 'THM_ENGINE', 'NumberTitle', 'off', 'Visible', 'off');
    else
        set(fig, 'Visible', 'off');
    end

    % 2. 해상도 픽셀 규격 지정 (가로 900, 세로 500)
    w = 900;
    h = 500;
    fig.Position = [100, 100, w, h];

    % 중첩 생성 방지 가드
    clf(fig);
    delete(findall(fig, 'type', 'axes'));

    % -----------------------------------------------------------------
    % [상단 그래프] 상습결빙구간 온도 모니터링
    % -----------------------------------------------------------------
    subplot(2, 1, 1);
    plot(1:data_len, temperatures, '-r', 'LineWidth', 2.5);
    title('상습결빙구간 온도 모니터링', 'FontSize', 12, 'FontWeight', 'bold');
    ylabel('온도 (\circC)', 'FontSize', 10);
    grid on;

    ax1 = gca;
    set_dynamic_axis(ax1, t_str, data_len);

    % -----------------------------------------------------------------
    % [하단 그래프] 상습결빙구간 습도 모니터링
    % -----------------------------------------------------------------
    subplot(2, 1, 2);
    plot(1:data_len, humidities, '-b', 'LineWidth', 2.5);
    title('상습결빙구간 습도 모니터링', 'FontSize', 12, 'FontWeight', 'bold');
    xlabel('시간 (Time Stamp ->)', 'FontSize', 10);
    ylabel('습도 (%)', 'FontSize', 10);
    grid on;

    ax2 = gca;
    set_dynamic_axis(ax2, t_str, data_len);

    drawnow limitrate;

    % 3. 🚨 [창 꺼짐 해결 핵심 패치] 🚨
    % QImage(RGB888)의 메모리 배열 구조와 일치하도록 가로/세로 차원을 올바르게 정렬합니다.
    frame = getframe(fig);
    img_matrix = frame.cdata;

    % MATLAB(행, 열, 채널) -> 파이썬 비트맵이 기대하는 표준 연속 배열로 변환
    img_permuted = permute(img_matrix, [2, 1, 3]);
    img_bytes = uint8(img_permuted(:));
end

function set_dynamic_axis(ax, t_str, data_len)
    if data_len <= 1
        ax.XLim = [0, 2];
        ax.XTick = 1;
        ax.XTickLabel = t_str;
        return;
    end

    if data_len > 30
        ax.XLim = [data_len - 30, data_len];
        raw_ticks = round(linspace(data_len - 30, data_len, 5));
    else
        ax.XLim = [1, max(2, data_len)];
        raw_ticks = round(linspace(1, data_len, min(5, data_len)));
    end

    ticks = unique(raw_ticks);
    ax.XTick = ticks;

    labels = repmat("", 1, length(ticks));
    for i = 1:length(ticks)
        idx = ticks(i);
        if idx >= 1 && idx <= data_len
            labels(i) = t_str(idx);
        end
    end
    ax.XTickLabel = labels;
end