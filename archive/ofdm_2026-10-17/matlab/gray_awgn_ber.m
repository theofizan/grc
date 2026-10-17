function probability = gray_awgn_ber(order, ebnoDB)
% Editing guide: docs/MODULAR_FLOWGRAPHS.md. Inputs/outputs use the units stated below.
%GRAY_AWGN_BER Exact coherent uncoded Gray BPSK/QPSK/square-QAM AWGN BER.
% T1-T4 in docs/THEORY.md. For QAM integrate every 1-D decision region
% and weight each transition by Gray-label Hamming distance. Unlike the
% nearest-neighbour approximation, this includes multiple-bit transitions.
% This implementation does not call berawgn (used separately as an oracle).
assert(ismember(order, [2 4 16 64]));
assert(all(isfinite(ebnoDB(:))));
gamma = 10.^(ebnoDB/10);
if order <= 4
    probability = 0.5*erfc(sqrt(gamma));
    return
end
bits = log2(order); side = sqrt(order); axisBits = bits/2;
levels = (-(side-1):2:side-1)/sqrt(2*(order-1)/3);
edges = [-Inf (levels(1:end-1)+levels(2:end))/2 Inf];
labels = bitxor(uint32(0:side-1), bitshift(uint32(0:side-1), -1));
probability = zeros(size(gamma));
for point = 1:numel(gamma)
    sigma = sqrt(1/(2*bits*gamma(point)));
    weightedErrors = 0;
    for transmitted = 1:side
        for decided = 1:side
            difference = bitxor(labels(transmitted), labels(decided));
            hamming = sum(bitget(difference, 1:axisBits));
            if hamming == 0, continue; end
            low = (edges(decided)-levels(transmitted))/sigma;
            high = (edges(decided+1)-levels(transmitted))/sigma;
            if low > 0
                mass = 0.5*(erfc(low/sqrt(2))-erfc(high/sqrt(2)));
            else
                mass = 0.5*(erfc(-high/sqrt(2))-erfc(-low/sqrt(2)));
            end
            weightedErrors = weightedErrors + hamming*mass;
        end
    end
    probability(point) = weightedErrors/(side*axisBits);
end
end
